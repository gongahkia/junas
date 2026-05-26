#!/usr/bin/env python3
"""LLM-assisted auto-labeler for legal-fixture .txt files.

Reads a fixture body, asks a strong reasoning model (default: o1) to enumerate
every PII / MNPI span the deterministic engine must detect and every defined-term
span it must NOT detect, and writes a labels.json with provenance fields so
downstream tooling can distinguish human ground-truth from model-derived
ground-truth.

INTEGRITY NOTE: the recall gate (scripts/recall_gate.py) reads labels uniformly.
Refreshing recall.lock.json from an auto-labeled corpus implicitly accepts model
judgment as truth — surface that in the --reason per item 16. Spot-check at
least 10% of auto-labeled fixtures before promoting baselines.

Usage:
    OPENAI_API_KEY=... python3 scripts/autolabel_fixture.py \\
        test/fixtures/legal-corpus/spa_02.txt
    OPENAI_API_KEY=... python3 scripts/autolabel_fixture.py \\
        test/fixtures/legal-corpus/spa_02.txt --model o1 --force
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import httpx

SG_POSTAL_LABEL_RE = re.compile(r"\b(?:Singapore|S)\s*(\d{6})\b", re.IGNORECASE)
SIX_DIGIT_RE = re.compile(r"\b\d{6}\b")
SG_NRIC_LABEL_RE = re.compile(r"^[STFGM]\d{7}[A-Z]$", re.IGNORECASE)
SG_UEN_LABEL_RE = re.compile(r"^(?:\d{8,9}[A-Z]|T\d{2}[A-Z]{2}\d{4}[A-Z])$")
FINANCIAL_AMOUNT_LABEL_RE = re.compile(
    r"(?:S\$|US\$|A\$|HK\$|[\$€£¥]|"
    r"\b(?:SGD|USD|EUR|GBP|JPY|AUD|HKD|KRW|CNY|RMB|MYR|IDR|THB|PHP|VND)\b\s*(?:S\$|US\$|A\$|HK\$|[\$€£¥])?)"
    r"\s*\d(?:[\d,]*\d)?(?:\.\d+)?(?:\s*(?:thousand|million|billion|trillion|[KMBT]))?"
    r"|\b\d(?:[\d,]*\d)?(?:\.\d+)?\s*(?:thousand|million|billion|trillion|[KMBT])\b",
    re.IGNORECASE,
)
PHONE_LABEL_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
NONPUBLIC_LABEL_RE = re.compile(
    r"\b(confidential|non-public|nonpublic|not yet public|not disclosed|undisclosed|"
    r"internal only|internal circulation only|internal use only|restricted|do not distribute|"
    r"should not be distributed externally|before announcement|pre-announcement|"
    r"quiet period|material non-public information|mnpi)\b",
    re.IGNORECASE,
)

PII_RULES = [
    "sg_nric_fin", "sg_uen", "sg_postal_address",
    "my_mykad", "id_nik", "th_national_id",
    "ph_philsys", "ph_tin", "vn_cccd",
    "passport_number", "email_address", "phone_number",
    "bank_account", "named_person", "sg_court_citation",
]
MNPI_RULES = [
    "material_event", "nonpublic_marker", "transaction_codename",
    "definitive_agreement", "material_adverse_change", "embargo_marker",
    "financial_amount", "financial_percentage", "large_number",
]
ALL_RULES = PII_RULES + MNPI_RULES

DOC_TYPE_TO_FIELD = {
    "spa": "SPA", "nda": "NDA", "sha": "SHA",
    "term_sheet": "term_sheet", "memo": "memo",
    "research_note": "research_note", "employment_letter": "generic",
}

SYSTEM = (
    "You are a precision labeler for a legal/finance PII/MNPI detection test "
    "harness. Given a synthetic legal-style document you must enumerate every "
    "span that should be detected as PII or MNPI, and every span that looks "
    "PII/MNPI-shaped but must NOT be detected because it is a defined term. "
    "Be exhaustive — list every distinct span, including all repeats. Never "
    "invent text that is not in the source verbatim."
)


def _infer_doc_type(p: Path) -> str:
    stem = p.stem
    if "_adv_" in stem:
        stem = stem.split("_adv_")[0]
    else:
        parts = stem.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            stem = parts[0]
    return DOC_TYPE_TO_FIELD.get(stem, "generic")


def _build_user_prompt(body: str, doc_type: str) -> str:
    return (
        f"Document type: {doc_type}\n"
        f"Source jurisdiction: SG\n\n"
        f"Valid PII rules: {', '.join(PII_RULES)}\n"
        f"Valid MNPI rules: {', '.join(MNPI_RULES)}\n\n"
        f"Return JSON in this exact shape:\n"
        f'{{"must_detect": [{{"rule": "<one-of-the-rules>", '
        f'"matched_text": "<verbatim span from doc>"}}, ...], '
        f'"must_not_detect": [{{"matched_text": "<defined-term span>", '
        f'"reason": "<one-line>"}}]}}\n\n'
        f"Rules:\n"
        f"1. matched_text MUST appear verbatim in the document (exact case, "
        f"exact characters, no surrounding whitespace).\n"
        f"2. List every distinct span. If the same value appears twice with "
        f"different casing (e.g. 'Share Purchase Agreement' and 'SHARE PURCHASE "
        f"AGREEMENT'), list both entries.\n"
        f"3. named_person: only people with honorifics (Dr/Mr/Ms/Mrs/Prof) OR "
        f"clearly named in a signature block. Do NOT label generic role nouns "
        f"like 'Vendor', 'Purchaser', 'the Company', 'the Seller'.\n"
        f"4. transaction_codename: 'Project <CapitalizedName>' pattern only "
        f"(e.g. 'Project Atlas', 'Project Pegasus').\n"
        f"5. definitive_agreement: Share Purchase Agreement / SPA / Shareholders "
        f"Agreement / SHA / APA / MOU / LOI / Term Sheet. List capitalised and "
        f"all-caps variants as separate entries.\n"
        f"6. material_adverse_change: 'Material Adverse Change' / 'Material "
        f"Adverse Effect' / explicit 'MAC clause' or 'MAE'. Do NOT label "
        f"'no MAC' / 'without any MAC' (those are negated).\n"
        f"7. embargo_marker: Signing Date / Closing Date / Effective Date / "
        f"Embargoed / Press Hold.\n"
        f"8. financial_amount: monetary values with currency (e.g. '$2.5 "
        f"billion', 'SGD 1,000,000', 'USD 50 million').\n"
        f"9. financial_percentage: percentage values (e.g. '15%', '12.5 per "
        f"cent').\n"
        f"10. sg_nric_fin: 9-char identifier matching ^[STFG]\\d{{7}}[A-Z]$.\n"
        f"11. sg_uen: legacy 9-char (^\\d{{8}}[A-Z]$) or T-format "
        f"(^T\\d{{2}}[A-Z]{{2}}\\d{{4}}[A-Z]$).\n"
        f"12. sg_postal_address: label only the 6-digit Singapore postal code "
        f"that follows Singapore/S, not the full street address.\n"
        f"13. must_not_detect: contract defined-term abbreviations such as "
        f"'(the \"Purchaser\")' → list 'Purchaser'; '(\"SPA\")' → list 'SPA'. "
        f"Include role-noun defined terms even if they do not appear in a "
        f"defining clause but the document treats them as roles (Vendor, "
        f"Purchaser, Seller, Buyer, the Company, the Parties).\n\n"
        f"DOCUMENT BODY:\n---\n{body}\n---\n\n"
        f"Return only the JSON object. No prose, no markdown fences."
    )


def _strip_boundary_punctuation(text: str, body: str) -> str:
    candidate = text.strip()
    for suffix in ("'s", "’s"):
        if candidate.endswith(suffix):
            shortened = candidate[:-len(suffix)].rstrip()
            if shortened and shortened in body:
                candidate = shortened
                break
    while candidate and candidate[-1] in ",;:.":
        shortened = candidate[:-1].rstrip()
        if not shortened or shortened not in body:
            break
        candidate = shortened
    return candidate


def _canonicalize_span(rule: str | None, text: str, body: str) -> str:
    candidate = _strip_boundary_punctuation(text, body)
    if rule == "sg_postal_address":
        match = SG_POSTAL_LABEL_RE.search(candidate)
        if match:
            return match.group(1)
        match = SIX_DIGIT_RE.search(candidate)
        if match:
            return match.group(0)
    if rule == "nonpublic_marker":
        match = NONPUBLIC_LABEL_RE.search(candidate)
        if match:
            return match.group(0)
    if rule == "financial_amount":
        match = FINANCIAL_AMOUNT_LABEL_RE.search(candidate)
        if match:
            return match.group(0)
    if rule == "phone_number":
        match = PHONE_LABEL_RE.search(candidate)
        if match:
            return match.group(0)
    return candidate


def _invalid_label_reason(rule: str, text: str) -> str:
    if rule == "sg_nric_fin" and not SG_NRIC_LABEL_RE.fullmatch(text):
        return "invalid Singapore NRIC/FIN shape"
    if rule == "sg_uen" and not SG_UEN_LABEL_RE.fullmatch(text):
        return "invalid Singapore UEN shape"
    if rule == "financial_amount" and not FINANCIAL_AMOUNT_LABEL_RE.fullmatch(text):
        return "unsupported financial amount shape"
    return ""


def _is_reasoning_model(model: str) -> bool:
    return model.startswith(("o1", "o3", "o4"))


def _chat_body(messages: list[dict], *, model: str) -> dict:
    body: dict = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    if _is_reasoning_model(model):
        body["max_completion_tokens"] = 16000  # reasoning models reserve tokens for thinking
    else:
        body["temperature"] = 0.0
        body["max_tokens"] = 4000
    return body


def _extract_message_content(payload: dict) -> str:
    content = payload["choices"][0]["message"].get("content") or ""
    if not content.strip():
        finish_reason = payload["choices"][0].get("finish_reason", "")
        raise RuntimeError(f"OpenAI returned empty content (finish_reason={finish_reason})")
    return content


def _call_openai(messages: list[dict], *, model: str, api_key: str) -> str:
    body = _chat_body(messages, model=model)
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=180.0,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"OpenAI {resp.status_code}: {resp.text[:800]}")
    return _extract_message_content(resp.json())


def _azure_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def label_model_for_provider(provider: str, model: str) -> str:
    if provider == "azure":
        deployment = _azure_env(
            "KAYPOH_AUTOLABEL_AZURE_DEPLOYMENT",
            "GPT5_MINI_DEPLOYMENT",
            "GPT5_PRO_DEPLOYMENT",
            "AZURE_OPENAI_DEPLOYMENT",
            "AZURE_DEPLOYMENT",
        )
        return f"azure:{deployment or model}"
    return f"openai:{model}"


def _call_azure_openai(messages: list[dict], *, model: str, api_key: str) -> tuple[str, str]:
    endpoint = _azure_env("KAYPOH_AUTOLABEL_AZURE_ENDPOINT", "GPT5_MINI_ENDPOINT", "GPT5_PRO_ENDPOINT")
    deployment = _azure_env("KAYPOH_AUTOLABEL_AZURE_DEPLOYMENT", "GPT5_MINI_DEPLOYMENT", "GPT5_PRO_DEPLOYMENT", "AZURE_OPENAI_DEPLOYMENT", "AZURE_DEPLOYMENT")
    api_version = _azure_env("KAYPOH_AUTOLABEL_AZURE_API_VERSION", "GPT5_MINI_API_VERSION", "GPT5_PRO_API_VERSION", "AZURE_OPENAI_API_VERSION")
    if not endpoint or not deployment or not api_version:
        raise RuntimeError("Azure autolabel provider requires endpoint, deployment, and api-version env vars")
    body = _chat_body(messages, model=model)
    body.pop("model", None)
    url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    resp = httpx.post(
        url,
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
        },
        json=body,
        timeout=180.0,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Azure OpenAI {resp.status_code}: {resp.text[:800]}")
    return _extract_message_content(resp.json()), deployment


def _call_model(messages: list[dict], *, model: str, provider: str, api_key: str) -> tuple[str, str]:
    if provider == "openai":
        return _call_openai(messages, model=model, api_key=api_key), model
    if provider == "azure":
        return _call_azure_openai(messages, model=model, api_key=api_key)
    raise ValueError(f"unknown autolabel provider: {provider}")


def _validate_labels(labels: dict, body: str) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    cleaned_must = []
    seen_must: set[tuple[str, str]] = set()
    for entry in labels.get("must_detect", []) or []:
        rule = entry.get("rule")
        text = entry.get("matched_text")
        if rule not in ALL_RULES:
            warnings.append(f"drop must_detect: invalid rule {rule!r} text={text!r}")
            continue
        if not isinstance(text, str) or not text:
            warnings.append(f"drop must_detect: empty text for rule {rule!r}")
            continue
        text = _canonicalize_span(rule, text, body)
        invalid_reason = _invalid_label_reason(rule, text)
        if invalid_reason:
            warnings.append(f"drop must_detect: {invalid_reason} rule={rule!r} text={text!r}")
            continue
        if text not in body:
            warnings.append(f"drop must_detect: text not verbatim rule={rule!r} text={text!r}")
            continue
        key = (rule, text)
        if key in seen_must:
            continue
        seen_must.add(key)
        cleaned_must.append({"rule": rule, "matched_text": text})
    cleaned_not = []
    seen_not: set[str] = set()
    for entry in labels.get("must_not_detect", []) or []:
        text = entry.get("matched_text")
        reason = entry.get("reason") or "defined term should not fire"
        if not isinstance(text, str) or not text:
            warnings.append("drop must_not_detect: empty text")
            continue
        text = _strip_boundary_punctuation(text, body)
        if SG_NRIC_LABEL_RE.fullmatch(text):
            warnings.append(f"drop must_not_detect: valid Singapore NRIC/FIN should be must_detect text={text!r}")
            continue
        if SG_UEN_LABEL_RE.fullmatch(text):
            warnings.append(f"drop must_not_detect: valid Singapore UEN should be must_detect text={text!r}")
            continue
        if text not in body:
            warnings.append(f"drop must_not_detect: text not verbatim text={text!r}")
            continue
        if text in seen_not:
            continue
        seen_not.add(text)
        cleaned_not.append({"matched_text": text, "reason": reason})
    return {"must_detect": cleaned_must, "must_not_detect": cleaned_not}, warnings


def _existing_is_human(labels_path: Path) -> bool:
    try:
        existing = json.loads(labels_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    if "_generation_note" in existing:
        return False  # stub from generate_legal_fixture.py — not yet hand-labeled
    if "_label_source" in existing:
        src = existing.get("_label_source", "")
        return not src.endswith("-auto")
    return True  # no provenance markers + not a stub → assume human


def autolabel(
    fixture_path: Path, *, model: str, api_key: str, force: bool = False, provider: str = "openai"
) -> dict:
    provider = provider.strip().lower()
    expected_label_model = label_model_for_provider(provider, model)
    body = fixture_path.read_text(encoding="utf-8")
    labels_path = fixture_path.with_suffix(".labels.json")
    if labels_path.exists():
        if _existing_is_human(labels_path):
            return {"status": "skipped_human_labeled", "path": str(labels_path)}
        if not force:
            try:
                existing = json.loads(labels_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = {}
            if existing.get("_label_model") in {model, expected_label_model}:
                return {"status": "skipped_same_model", "path": str(labels_path)}
    doc_type = _infer_doc_type(fixture_path)
    user = _build_user_prompt(body, doc_type)
    raw, label_model = _call_model(
        [{"role": "user", "content": SYSTEM + "\n\n" + user}],
        model=model,
        provider=provider,
        api_key=api_key,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"status": "error", "error": f"json parse: {exc}", "raw": raw[:500]}
    cleaned, warnings = _validate_labels(parsed, body)
    out = {
        "doc_id": fixture_path.stem,
        "document_type": doc_type,
        "source_jurisdiction": "SG",
        "destination_jurisdiction": "SG",
        "must_detect": cleaned["must_detect"],
        "must_not_detect": cleaned["must_not_detect"],
        "_label_source": f"{provider}:{label_model}-auto",
        "_label_model": f"{provider}:{label_model}",
        "_label_warnings": warnings,
        "_label_note": (
            "AUTO-LABELED by LLM. Spot-check before refreshing recall.lock.json. "
            "Lock updates must include this provenance in --reason per item 16."
        ),
    }
    labels_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "labeled",
        "path": str(labels_path),
        "must_detect_count": len(cleaned["must_detect"]),
        "must_not_detect_count": len(cleaned["must_not_detect"]),
        "warnings": len(warnings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM auto-labeler for fixtures")
    parser.add_argument("fixture_path", help="Path to fixture .txt file")
    parser.add_argument(
        "--model",
        default=os.environ.get("KAYPOH_AUTOLABEL_MODEL", "o1"),
        help="OpenAI model (default: o1, env KAYPOH_AUTOLABEL_MODEL)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-label even if labels.json already exists (will not overwrite human labels)",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "azure"),
        default=os.environ.get("KAYPOH_AUTOLABEL_PROVIDER", "openai"),
        help="Model provider (default: openai, env KAYPOH_AUTOLABEL_PROVIDER)",
    )
    args = parser.parse_args(argv)
    if args.provider == "azure":
        api_key = _azure_env("KAYPOH_AUTOLABEL_AZURE_API_KEY", "GPT5_MINI_API_KEY", "GPT5_PRO_API_KEY", "AZURE_OPENAI_API_KEY")
    else:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print(f"{args.provider} API key not set", file=sys.stderr)
        return 2
    result = autolabel(
        Path(args.fixture_path), model=args.model, api_key=api_key, force=args.force, provider=args.provider
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("status", "").startswith(("labeled", "skipped")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
