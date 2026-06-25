#!/usr/bin/env python3
"""Smoke-test audit-pack export and verification end to end."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _seed_review(review_id: str) -> None:
    from junas.review import decisions, journal

    importlib.reload(journal)
    importlib.reload(decisions)
    decisions.start_review_session(
        review_id=review_id,
        text_hash="smoke-text-hash",
        document_type="email",
        source_jurisdiction="SG",
        destination_jurisdiction="US",
        findings=[
            {
                "id": "f1",
                "category": "PII",
                "rule": "named_person",
                "severity": "high",
                "matched_text": "Dr Jane Tan",
                "start_char": 0,
                "end_char": 11,
            },
        ],
    )
    decisions.record_decision(
        review_id=review_id,
        decision=decisions.Decision(
            finding_id="f1",
            action="accept",
            rationale="raw rationale smoke secret",
            reviewer_id="smoke-reviewer",
        ),
    )


def run_smoke(output_dir: Path | None = None) -> tuple[bool, dict]:
    with tempfile.TemporaryDirectory(prefix="junas-audit-smoke-") as tmp:
        work = output_dir or Path(tmp)
        work.mkdir(parents=True, exist_ok=True)
        journal_dir = work / "journal"
        pack = work / "audit-pack-smoke.zip"
        review_id = "audit-smoke-review"
        env = {
            **os.environ,
            "PYTHONPATH": str(SRC),
            "JUNAS_JOURNAL_DIR": str(journal_dir),
            "JUNAS_JOURNAL_KEY": "audit-smoke-key",
            "JUNAS_AUDIT_MIN_WAIT_SECONDS": "",
        }
        with patch.dict(os.environ, env, clear=False):
            _seed_review(review_id)
        export = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "export_audit_pack.py"),
                review_id,
                "--output",
                str(pack),
                "--include-defensibility",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
        )
        verify = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_audit_pack.py"), str(pack)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
        )
        archive_ok = False
        if pack.exists():
            with zipfile.ZipFile(pack) as archive:
                names = set(archive.namelist())
                findings = archive.read("findings.json").decode("utf-8")
                manifest = json.loads(archive.read("manifest.json"))
                archive_ok = (
                    {"manifest.json", "journal.jsonl", "findings.json", "decisions.json"}.issubset(names)
                    and manifest.get("journal_chain_status") == "valid"
                    and "Dr Jane Tan" in findings
                )
        ok = (
            export.returncode == 0
            and verify.returncode == 0
            and pack.exists()
            and archive_ok
        )
        payload = {
            "ok": ok,
            "pack_path": str(pack),
            "export_returncode": export.returncode,
            "verify_returncode": verify.returncode,
            "verify_stdout": verify.stdout.strip(),
            "export_stderr": export.stderr.strip(),
            "verify_stderr": verify.stderr.strip(),
        }
        if output_dir is not None:
            return ok, payload
        return ok, {**payload, "pack_path": ""}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test audit-pack export and verification")
    parser.add_argument("--output-dir", type=Path, help="keep generated smoke artifacts in this directory")
    args = parser.parse_args(argv)
    ok, payload = run_smoke(args.output_dir)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
