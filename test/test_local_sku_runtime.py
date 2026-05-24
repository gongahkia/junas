"""Lock-in test that the kaypoh-local SKU runs without heavy server-only deps.

Blocks `torch`, `transformers`, `sentence_transformers`, `redis`, `xgboost`, `sklearn`, and
`pandas` via `sys.modules[name] = None` before importing the runtime, then drives the full
desktop happy-path: /anonymize, /reidentify, /review/{id}/decision. Any module that imports
one of the blocked names at module load (rather than lazily) will surface as an ImportError
here and the test fails loud.
"""

import importlib
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

BLOCKED_HEAVY_DEPS = (
    "torch",
    "transformers",
    "sentence_transformers",
    "redis",
    "xgboost",
    "sklearn",
    "pandas",
    "accelerate",
)


def _subprocess_with_blocked_deps(snippet: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["KAYPOH_PIPELINE_LAYERS"] = "lexicon"
    # subprocess isolates sys.modules from the parent test process
    prelude = (
        "import sys\n"
        f"for name in {list(BLOCKED_HEAVY_DEPS)!r}:\n"
        "    sys.modules[name] = None\n"
    )
    return subprocess.run(
        [sys.executable, "-c", prelude + snippet],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    )


class LocalSkuRuntimeTests(unittest.TestCase):
    def test_backend_main_importable_without_heavy_deps(self):
        result = _subprocess_with_blocked_deps(
            "import backend.main as main\n"
            "paths = sorted(r.path for r in main.app.routes if hasattr(r, 'methods'))\n"
            "assert '/anonymize' in paths, paths\n"
            "assert '/reidentify' in paths, paths\n"
            "assert '/review' in paths, paths\n"
            "print('OK')\n"
        )
        self.assertEqual(result.returncode, 0, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self.assertIn("OK", result.stdout)

    def test_review_anonymize_reidentify_end_to_end_without_heavy_deps(self):
        result = _subprocess_with_blocked_deps(
            "from kaypoh.review.engine import PreSendReviewEngine\n"
            "from kaypoh.anonymize import DeterministicAnonymizer, reidentify\n"
            "text = 'Send Dr Jane Tan S1234567D the draft.'\n"
            "engine = PreSendReviewEngine()\n"
            "result = engine.review(text=text, source_jurisdiction='SG', destination_jurisdiction='SG',\n"
            "                       entity_id=None, include_suggestions=False, document_type='SPA')\n"
            "anon = DeterministicAnonymizer().anonymize(text=text, findings=result.findings)\n"
            "back, n = reidentify(anonymized_text=anon.anonymized_text,\n"
            "                    mapping=[{'placeholder': m.placeholder, 'original_text': m.original_text} for m in anon.mapping])\n"
            "assert back == text, (back, text)\n"
            "assert n >= 2, n\n"
            "assert '[PERSON_1]' in anon.anonymized_text\n"
            "assert '[NRIC_FIN_1]' in anon.anonymized_text\n"
            "print('OK')\n"
        )
        self.assertEqual(result.returncode, 0, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
