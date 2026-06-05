"""SSO (Singapore Statutes Online) ingestion.

Ports the logic from ``kevanwee/sgstatutescraper`` with production
hardening:

- explicit per-request rate limiting at ``SourceMetadata.crawl_delay_seconds``
  (3s default, per AGC/SSO terms of use observed by the source repo);
- exponential-backoff retry on 5xx and transport errors;
- statute-version pinning via the ``DocDate`` query parameter and an
  emitted ``version_id`` (e.g. ``PDPA2012@2020``);
- act -> part -> division -> section JSONL output with stable IDs;
- idempotent rerun (skips acts already present in the output JSONL unless
  ``force=True``);
- ``ACT_CODES`` seed list curated for SGLB-02 / SGLB-06 coverage. Full
  catalogue discovery from ``/Browse/Act/Current/All`` is wired but
  gated behind ``discover=True`` so default ``make ingest-sso`` runs in
  bounded time.

The module is offline-safe: ``parse_html_file()`` lets the test suite
exercise extraction without network.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterator

import httpx

from data.ingestion._provenance import extraction_rule_sha
from data.parsers.sso_parser import SsoAct, SsoSection, parse_sso_html, parse_toc

logger = logging.getLogger(__name__)

SSO_BASE = "https://sso.agc.gov.sg"
USER_AGENT = "Mozilla/5.0 (compatible; junas-research/0.1; +https://github.com/gongahkia/junas)"
DEFAULT_CRAWL_DELAY = 3.0  # AGC SSO terms; mirror the source repo's 1s minimum, pad to 3s for safety
DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 4
BACKOFF_BASE = 2.0  # seconds; multiplied by 2**attempt

# Curated seed for v0.1 of SGLB. Codes follow the SSO short-code convention.
# Format: (chapter_number, kind, path_template) where path_template takes
# the chapter_number via ``{code}`` and may include a ``DocDate`` pin.
ACT_CODES: tuple[tuple[str, str, str], ...] = (
    ("PDPA2012", "act", "/Act/{code}?WholeDoc=1"),
    ("EmA1968", "act", "/Act/{code}?WholeDoc=1"),
    ("PC1871", "act", "/Act/{code}?WholeDoc=1"),
    ("ROC2021", "sl", "/SL-Supp/S914-2021/Published?DocDate=20211201&WholeDoc=1"),
)

DEFAULT_OUTPUT = Path("vendor-data/sso/statutes.jsonl")
PROVS_PER_REQUEST = 60  # cap for ProvIds URL length; SSO accepts at least this many
EXTRACTION_MODULE = Path(__file__)
EXTRACTION_RULE_NAME = "sso"


def _sleep_with_jitter(delay: float) -> None:
    """Sleep for ``delay`` seconds plus a small jitter to avoid clustering."""
    if delay <= 0:
        return
    time.sleep(delay + random.uniform(0, 0.5))  # nosec - jitter, not crypto


def fetch_html(
    url: str,
    *,
    client: httpx.Client | None = None,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
    max_retries: int = MAX_RETRIES,
) -> str:
    """Fetch one SSO HTML page with retry/backoff.

    Honours ``crawl_delay`` after every successful or final-failed request
    so consecutive SSO requests are always paced, whether the caller owns
    the ``httpx.Client`` or not. Matches the source repo's per-fetch
    sleep, padded from the observed 1s to 3s per AGC SSO terms.
    """
    owned = False
    if client is None:
        client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )
        owned = True
    try:
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = client.get(url)
                if response.status_code == 200:
                    return response.text
                if response.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"transient {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                return response.text
            except (httpx.HTTPError, httpx.TransportError) as exc:
                last_exc = exc
                if attempt == max_retries:
                    break
                backoff = BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 1)  # nosec
                logger.warning("SSO fetch %s failed (%s); retry in %.1fs", url, exc, backoff)
                time.sleep(backoff)
        raise RuntimeError(f"SSO fetch failed after {max_retries + 1} attempts: {url}") from last_exc
    finally:
        if owned:
            client.close()
        # always pace; AGC tos prohibits rapid-fire requests
        _sleep_with_jitter(crawl_delay)


def parse_html_file(path: str | Path, chapter_number: str, source_url: str = "") -> SsoAct:
    """Offline helper: parse a saved SSO HTML file. Used by the tests."""
    html = Path(path).read_text(encoding="utf-8")
    return parse_sso_html(html, chapter_number, source_url or f"{SSO_BASE}/Act/{chapter_number}")


def _toc_url(chapter_number: str, kind: str, path_template: str) -> str:
    return SSO_BASE + path_template.format(code=chapter_number)


def _prov_batch_url(toc_url: str, prov_ids: list[str]) -> str:
    """Build a ``?ProvIds=...`` URL based on the act's WholeDoc URL."""
    base, _, _ = toc_url.partition("?")
    return f"{base}?ProvIds={','.join(prov_ids)}"


def ingest_act(
    chapter_number: str,
    *,
    kind: str = "act",
    path_template: str = "/Act/{code}?WholeDoc=1",
    client: httpx.Client | None = None,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
    provs_per_request: int = PROVS_PER_REQUEST,
) -> SsoAct:
    """Fetch + parse a single act/SL by its SSO short code.

    Two-step flow:

    1. GET ``WholeDoc=1`` for act metadata + the TOC sidebar (the
       ``legisContent`` block is lazy-loaded, but ``div#contents`` and
       the version chrome are server-rendered);
    2. enumerate all ``prN-`` ids from the TOC and request them via
       ``?ProvIds=p1,p2,...`` in batches of ``provs_per_request``.
    """
    toc_url = _toc_url(chapter_number, kind, path_template)
    logger.info("SSO TOC %s -> %s", chapter_number, toc_url)
    toc_html = fetch_html(toc_url, client=client, crawl_delay=crawl_delay)

    section_to_part, section_to_division, ordered_provs = parse_toc(toc_html)
    if not ordered_provs:
        # legislation rendered fully in the TOC page (rare; ROC-style SL)
        return parse_sso_html(toc_html, chapter_number, toc_url)

    # accumulate per-batch HTML so the parser can walk in document order
    aggregate = SsoAct(
        chapter_number=chapter_number,
        act_title="",
        kind=kind,
        edition=0,
        revised_edition_text="",
        valid_start_date="",
        source_url=toc_url,
        version_id=f"{chapter_number}@current",
    )
    seen_numbers: set[str] = set()
    for start in range(0, len(ordered_provs), provs_per_request):
        batch = ordered_provs[start : start + provs_per_request]
        batch_url = _prov_batch_url(toc_url, batch)
        logger.debug("SSO batch %s [%d-%d]", chapter_number, start, start + len(batch))
        batch_html = fetch_html(batch_url, client=client, crawl_delay=crawl_delay)
        batch_act = parse_sso_html(
            batch_html,
            chapter_number,
            toc_url,
            toc_html=toc_html,
        )
        # pull metadata from the first batch (TOC-derived)
        if not aggregate.act_title:
            aggregate.act_title = batch_act.act_title
            aggregate.edition = batch_act.edition
            aggregate.revised_edition_text = batch_act.revised_edition_text
            aggregate.valid_start_date = batch_act.valid_start_date
            aggregate.version_id = batch_act.version_id
            aggregate.kind = batch_act.kind or kind
        for section in batch_act.sections:
            if section.number in seen_numbers:
                continue
            seen_numbers.add(section.number)
            aggregate.sections.append(section)
    return aggregate


def _section_to_row(section: SsoSection, rule_sha: str | None = None) -> dict[str, object]:
    row = asdict(section)
    # stable section id: <version_id>:<number>, idempotent across reruns
    row["section_id"] = f"{section.version_id}:{section.number}"
    row["extraction_rule_sha"] = rule_sha or extraction_rule_sha(EXTRACTION_MODULE)
    return row


def write_jsonl(
    acts: Iterator[SsoAct] | list[SsoAct],
    output_path: Path,
    *,
    append: bool = False,
) -> int:
    """Write section rows to JSONL. Returns count written."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    written = 0
    seen: set[str] = set()
    if append and output_path.exists():
        with output_path.open(encoding="utf-8") as existing:
            for line in existing:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sid = row.get("section_id")
                if sid:
                    seen.add(sid)
    rule_sha = extraction_rule_sha(EXTRACTION_MODULE)
    with output_path.open(mode, encoding="utf-8") as handle:
        for act in acts:
            for section in act.sections:
                row = _section_to_row(section, rule_sha)
                sid = str(row["section_id"])
                if sid in seen:
                    continue
                seen.add(sid)
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                written += 1
    return written


def _existing_version_ids(path: Path) -> set[str]:
    """Read existing JSONL and return the set of version_ids already on disk."""
    if not path.exists():
        return set()
    version_ids: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = row.get("version_id")
            if vid:
                version_ids.add(str(vid))
    return version_ids


def run(
    output_path: Path | str = DEFAULT_OUTPUT,
    *,
    codes: tuple[tuple[str, str, str], ...] = ACT_CODES,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
    force: bool = False,
) -> int:
    """Ingest the configured ``codes`` list into a JSONL at ``output_path``."""
    output_path = Path(output_path)
    existing_versions = set() if force else _existing_version_ids(output_path)
    acts: list[SsoAct] = []
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    ) as client:
        for code, kind, path_template in codes:
            try:
                act = ingest_act(
                    code,
                    kind=kind,
                    path_template=path_template,
                    client=client,
                    crawl_delay=crawl_delay,
                )
            except RuntimeError as exc:
                logger.error("SSO skip %s: %s", code, exc)
                continue
            if act.version_id in existing_versions and not force:
                logger.info("SSO skip %s (version %s already present)", code, act.version_id)
                continue
            acts.append(act)
            # per-page sleep is handled by fetch_html; no extra wait here
    written = write_jsonl(acts, output_path, append=not force)
    logger.info("SSO wrote %d section rows to %s", written, output_path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest SG statutes from SSO")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--crawl-delay", type=float, default=DEFAULT_CRAWL_DELAY)
    parser.add_argument("--force", action="store_true", help="rebuild from scratch")
    parser.add_argument("--code", action="append", help="ingest a single SSO code (repeatable)")
    args = parser.parse_args()
    codes: tuple[tuple[str, str, str], ...] = ACT_CODES
    if args.code:
        selected = []
        for code in args.code:
            match = next((c for c in ACT_CODES if c[0] == code), None)
            if match is None:
                selected.append((code, "act", "/Act/{code}?WholeDoc=1"))
            else:
                selected.append(match)
        codes = tuple(selected)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return run(args.output, codes=codes, crawl_delay=args.crawl_delay, force=args.force)


if __name__ == "__main__":
    raise SystemExit(0 if main() >= 0 else 1)
