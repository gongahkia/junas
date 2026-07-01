import importlib
import json
import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from junas.review.engine import ReviewFinding
from junas.review.surfacing_lane import apply_surfacing_lanes, lane_review_id
from scripts.update_lane import update_lane_config


@asynccontextmanager
async def _noop_lifespan(app):
    yield


def _finding(finding_id: str, severity: str, score: float) -> ReviewFinding:
    return ReviewFinding(
        id=finding_id,
        category="MNPI",
        rule="material_event",
        jurisdiction="SG",
        severity=severity,
        score=score,
        matched_text="Acme acquisition",
        start_char=0,
        end_char=16,
        reason="test",
        legal_basis="SG_SFA_MARKET_MISCONDUCT",
    )


class SurfacingLaneModuleTests(unittest.TestCase):
    def test_lane_config_tags_and_partitions_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["JUNAS_TENANT_CONFIG_DIR"] = tmp
            try:
                Path(tmp, "tenant-a.toml").write_text(
                    "[lane.medium]\nroute = \"batched\"\ndigest_cadence = \"daily\"\n",
                    encoding="utf-8",
                )
                findings = [_finding("medium-1", "medium", 55.0), _finding("high-1", "high", 85.0)]
                result = apply_surfacing_lanes(findings, tenant_id="tenant-a")
            finally:
                os.environ.pop("JUNAS_TENANT_CONFIG_DIR", None)

        self.assertEqual([f.id for f in result.visible_findings], ["high-1"])
        self.assertEqual([f.id for f in result.suppressed_findings], ["medium-1"])
        lane = result.suppressed_findings[0].metadata["lane_routing"]
        self.assertEqual(lane["route"], "batched")
        self.assertTrue(lane["suppressed"])
        self.assertEqual(lane["digest_cadence"], "daily")

    def test_threshold_gated_lane_surfaces_scores_at_or_above_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["JUNAS_TENANT_CONFIG_DIR"] = tmp
            try:
                Path(tmp, "tenant-a.toml").write_text(
                    "[lane.medium]\nroute = \"threshold_gated\"\nthreshold_value = 55\n",
                    encoding="utf-8",
                )
                findings = [_finding("low-score", "medium", 54.0), _finding("at-threshold", "medium", 55.0)]
                result = apply_surfacing_lanes(findings, tenant_id="tenant-a")
            finally:
                os.environ.pop("JUNAS_TENANT_CONFIG_DIR", None)

        self.assertEqual([f.id for f in result.visible_findings], ["at-threshold"])
        self.assertEqual([f.id for f in result.suppressed_findings], ["low-score"])

    def test_high_findings_cannot_be_suppressed_by_lane_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["JUNAS_TENANT_CONFIG_DIR"] = tmp
            try:
                Path(tmp, "tenant-a.toml").write_text(
                    "[lane.high]\nroute = \"batched\"\ndigest_cadence = \"daily\"\n",
                    encoding="utf-8",
                )
                result = apply_surfacing_lanes([_finding("high-1", "high", 91.0)], tenant_id="tenant-a")
            finally:
                os.environ.pop("JUNAS_TENANT_CONFIG_DIR", None)

        self.assertEqual([f.id for f in result.visible_findings], ["high-1"])
        self.assertEqual(result.suppressed_findings, [])
        self.assertEqual(result.visible_findings[0].metadata["lane_routing"]["reason"], "deterministic_high_visible")


class SurfacingLaneApiTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        credentials = {
            "reviewer-key": {
                "tenant_id": "tenant-a",
                "subject": "reviewer",
                "roles": ["reviewer"],
            },
            "checker-key": {
                "tenant_id": "tenant-a",
                "subject": "checker",
                "roles": ["checker"],
            },
            "admin-key": {
                "tenant_id": "tenant-a",
                "subject": "admin",
                "roles": ["reviewer", "admin"],
            },
        }
        self._env = {
            "JUNAS_TENANCY_ENABLED": "1",
            "JUNAS_TENANCY_AUTH_MODES": "api_key",
            "JUNAS_TENANT_CREDENTIALS_JSON": json.dumps(credentials),
            "JUNAS_TENANT_CONFIG_DIR": str(self.tmpdir / "tenant-config"),
            "JUNAS_JOURNAL_DIR": str(self.tmpdir / "journal"),
            "JUNAS_JOURNAL_KEY": "lane-test-key",
            "JUNAS_REVIEW_PERSIST": "1",
            "JUNAS_MAPPING_STORE_KEY": "q5cVCBcQ0PHsgxBpwoXOrp0tGSgZBz7oBfZmuZBFLJk=",
            "JUNAS_SUBJECT_INDEX_KEY": "subject-index-test-key",
        }
        self._old_env = {key: os.environ.get(key) for key in self._env}
        os.environ.update(self._env)
        update_lane_config(
            tenant="tenant-a",
            severity="medium",
            route="batched",
            threshold_value=None,
            digest_cadence="daily",
            reason="tenant wants medium findings in daily digest",
            actor="test",
        )
        import junas.backend.main as main_mod
        import junas.review.decisions as decisions_mod
        import junas.review.journal as journal_mod

        importlib.reload(journal_mod)
        importlib.reload(decisions_mod)
        importlib.reload(main_mod)
        self.main = main_mod
        self.main.app.router.lifespan_context = _noop_lifespan
        self.main._state.clear()
        self.main.app.openapi_schema = None
        self.journal = journal_mod

    def tearDown(self):
        self._tmpdir.cleanup()
        for key, old_value in self._old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
        import junas.backend.main as main_mod

        importlib.reload(main_mod)

    def test_default_review_hides_lane_suppressed_findings_but_admin_can_inspect(self):
        with TestClient(self.main.app) as client:
            response = client.post(
                "/review",
                headers={"X-API-Key": "reviewer-key"},
                json={
                    "text": "Acme acquisition for $2.5 billion is pending.",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "memo",
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["findings"], [])
            self.assertEqual(payload["lane_suppressed_count"], 2)
            self.assertEqual(payload["lane_suppressed_findings"], [])

            checker_state = client.get(
                f"/review/{payload['request_id']}",
                headers={"X-API-Key": "checker-key"},
            )
            self.assertEqual(checker_state.status_code, 200, checker_state.text)
            self.assertEqual(checker_state.json()["findings"], [])
            self.assertEqual(checker_state.json()["lane_suppressed_count"], 2)
            self.assertEqual(checker_state.json()["lane_suppressed_findings"], [])

            admin_state = client.get(
                f"/review/{payload['request_id']}",
                headers={"X-API-Key": "admin-key"},
            )
            self.assertEqual(admin_state.status_code, 200, admin_state.text)
            admin_payload = admin_state.json()
            self.assertEqual(admin_payload["findings"], [])
            self.assertEqual(len(admin_payload["lane_suppressed_findings"]), 2)
            lane = admin_payload["lane_suppressed_findings"][0]["metadata"]["lane_routing"]
            self.assertTrue(lane["suppressed"])
            self.assertEqual(lane["route"], "batched")

    def test_lane_update_is_journaled(self):
        entries = self.journal.read_journal(review_id=lane_review_id("tenant-a"), tenant_id="tenant-a")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].event_type, "lane_config_updated")
        self.assertEqual(entries[0].payload["reason"], "tenant wants medium findings in daily digest")


if __name__ == "__main__":
    unittest.main()
