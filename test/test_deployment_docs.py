import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent


def load_retention_checker():
    path = ROOT / "scripts" / "check_retention_manifest.py"
    spec = importlib.util.spec_from_file_location("test_check_retention_manifest", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load retention checker from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DeploymentDocsTests(unittest.TestCase):
    def test_subject_erasure_runbook_names_backfill_and_retention_limits(self):
        text = (ROOT / "docs" / "deployment-hardening.md").read_text(encoding="utf-8")

        self.assertIn("Subject Erasure Runbook", text)
        self.assertIn("docs/security/subject-erasure.md", text)
        self.assertIn("--backfill", text)
        self.assertIn("--dry-run", text)
        self.assertIn("subject_erasure_recorded", text)
        self.assertIn("SIEM exports", text)
        self.assertIn("backups", text)
        self.assertIn("retention", text)

    def test_subject_erasure_doc_covers_deleted_tombstoned_retained_delegated_artifacts(self):
        text = (ROOT / "docs" / "security" / "subject-erasure.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("security/subject-erasure.md", docs_index)
        for token in (
            "Persisted mapping files",
            "Deleted",
            "Subject index bucket",
            "Review journal entries",
            "Tombstoned",
            "Audit packs",
            "Retained or expired by operator policy",
            "SIEM exports",
            "Delegated",
            "Backups and cold archives",
            "scripts/erase_subject.py",
            "scripts/verify_journal.py",
            "scripts/check_fixture_scrub.py",
            "subject_erasure_recorded",
            "deleted_mapping_documents",
            "journaled_review_sessions",
            "removed_index_entries",
        ):
            self.assertIn(token, text)

    def test_remote_llm_config_doc_covers_raw_text_opt_in_and_privacy_ledger(self):
        text = (ROOT / "docs" / "security" / "remote-llm-config.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        install = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
        governance = (ROOT / "docs" / "llm-governance.md").read_text(encoding="utf-8")

        self.assertIn("security/remote-llm-config.md", docs_index)
        self.assertIn("docs/security/remote-llm-config.md", install)
        self.assertIn("docs/security/remote-llm-config.md", governance)
        for token in (
            "allow_remote_base_url = true",
            "allow_remote_raw_text = false",
            "llm_input_mode = \"structured_tokens\"",
            "llm_input_mode = \"raw_text\"",
            "allow_remote_raw_text = true",
            "tenant_opt_in_openai = true",
            "tenant_opt_in_azure_openai = true",
            "JUNAS_LLM_ALLOW_REMOTE_RAW_TEXT",
            "JUNAS_LLM_TENANT_OPT_IN_OPENAI",
            "JUNAS_LLM_TENANT_OPT_IN_AZURE_OPENAI",
            "JUNAS_LLM_AZURE_API_VERSION",
            "privacy_ledger",
            "test/test_structured_tokens_llm.py",
            "test/test_siem_export.py",
        ):
            self.assertIn(token, text)

    def test_retention_manifest_doc_example_matches_checker_schema(self):
        text = (ROOT / "docs" / "deployment-hardening.md").read_text(encoding="utf-8")
        match = re.search(r"## Retention Manifest.*?```json\n(?P<body>.*?)\n```", text, re.S)
        self.assertIsNotNone(match)
        example = json.loads(match.group("body"))
        checker = load_retention_checker()
        controls = set(example["controls"])

        self.assertEqual(controls, set(checker.REQUIRED_CONTROLS))
        self.assertEqual(example["schema_version"], "junas.retention_manifest.v1")
        for control in controls:
            result = checker._evaluate_control(control, example["controls"][control])
            self.assertEqual(result["status"], "configured", msg=f"{control}: {result}")
        for token in ("retention_days", "delete_after_days", "retain_for_days", "policy", "external_policy_ref"):
            self.assertIn(token, text)
        self.assertIn("docs/security/data-retention.md", text)
        self.assertIn("scripts/check_retention_manifest.py --manifest", text)
        self.assertIn("--json", text)

    def test_deployment_hardening_has_backend_first_reference_architecture(self):
        text = (ROOT / "docs" / "deployment-hardening.md").read_text(encoding="utf-8")

        for token in (
            "## Backend-First Reference Architecture",
            "FastAPI backend",
            "Reverse proxy/TLS",
            "API key / JWT / mTLS auth",
            "Versioned policy config",
            "No-body process logs",
            "SIEM export",
            "JUNAS_JOURNAL_DIR",
            "Encrypted backup + retention manifest",
            "Optional adapters",
            "Outlook Smart Alerts",
            "Browser GenAI extension",
            "Word taskpane",
            "DMS upload hook",
            "direct API plus one supported workflow adapter",
        ):
            self.assertIn(token, text)

    def test_deployment_hardening_compares_deployment_modes(self):
        text = (ROOT / "docs" / "deployment-hardening.md").read_text(encoding="utf-8")

        for token in (
            "## Deployment Mode Comparison",
            "| Hosted server |",
            "| Customer-managed Docker |",
            "| Offline local daemon |",
            "| Hybrid local-plus-server |",
            "reverse proxy/TLS",
            "tenant auth",
            "versioned policy config",
            "SIEM export",
            "customer-held `JUNAS_JOURNAL_KEY`",
            "`JUNAS_MAPPING_STORE_KEY`",
            "`JUNAS_SUBJECT_INDEX_KEY`",
            "retention manifest",
            "backup/restore",
            "http://127.0.0.1:8765",
            "Server remains the policy/audit source",
            "docs/install.md",
        ):
            self.assertIn(token, text)

    def test_admin_console_requirements_define_scope(self):
        text = (ROOT / "docs" / "admin-console" / "requirements.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("admin-console/requirements.md", docs_index)
        for token in (
            "Admin Console Requirements",
            "requirements only",
            "review sessions",
            "decisions",
            "policy config",
            "audit exports",
            "False-positive triage",
            "tenant health",
            "backend remains the trust",
            "tenant-scoped",
            "no raw body exposure by default",
            "review_id",
            "policy_id",
            "policy_version",
            "Draft",
            "validate",
            "publish",
            "rollback",
            "scripts/export_audit_pack.py",
            "scripts/verify_audit_pack.py",
            "scripts/verify_journal.py",
            "adapter telemetry",
            "retention manifest",
            "No frontend framework dependency",
        ):
            self.assertIn(token, text)

    def test_admin_console_adr_keeps_ui_docs_only_until_validation(self):
        text = (
            ROOT / "docs" / "adr" / "0005-admin-console-docs-only-until-validation.md"
        ).read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("adr/0005-admin-console-docs-only-until-validation.md", docs_index)
        for token in (
            "ADR 0005: Admin Console Docs-Only Until Validation",
            "Status: Accepted",
            "docs-only until customer validation",
            "separate frontend",
            "server-rendered FastAPI templates",
            "frontend framework dependency",
            "no-build prototype",
            "review sessions",
            "decisions",
            "policy config",
            "audit exports",
            "false-positive triage",
            "tenant health",
            "FastAPI backend remains the trust boundary",
            "no raw body exposure by default",
            "tenant isolation",
            "local-dev-only headers",
            "Revisit Triggers",
        ):
            self.assertIn(token, text)

    def test_admin_console_review_session_list_endpoint_requirements(self):
        text = (
            ROOT / "docs" / "admin-console" / "review-session-list-endpoint.md"
        ).read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        requirements = (ROOT / "docs" / "admin-console" / "requirements.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("admin-console/review-session-list-endpoint.md", docs_index)
        self.assertIn("docs/admin-console/review-session-list-endpoint.md", requirements)
        for token in (
            "Review Session List Endpoint Requirements",
            "GET /admin/review-sessions",
            "read-only list of review-session metadata",
            "Allowed production roles",
            "`admin`",
            "`auditor`",
            "`checker`",
            "local-dev-only reviewer headers",
            "credential-derived tenant",
            "must not accept `tenant_id`",
            "cursor from another tenant",
            "`limit`",
            "maximum 100",
            "`cursor`",
            "opaque server-generated cursor",
            "`decision`",
            "`required_action`",
            "No raw body exposure by default",
            "no raw content or matched text",
            "pagination stability",
            "tenant isolation",
            "role checks",
            "`matched_text`",
            "`original_text`",
            "`recipient`",
            "`filename`",
        ):
            self.assertIn(token, text)

    def test_admin_console_policy_config_ui_requirements(self):
        text = (ROOT / "docs" / "admin-console" / "policy-config-ui.md").read_text(
            encoding="utf-8"
        )
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        requirements = (ROOT / "docs" / "admin-console" / "requirements.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("admin-console/policy-config-ui.md", docs_index)
        self.assertIn("docs/admin-console/policy-config-ui.md", requirements)
        for token in (
            "Policy Config UI Requirements",
            "versioned Junas policy profiles",
            "Create drafts",
            "validate drafts",
            "publish validated drafts",
            "rollback to prior versions",
            "local-dev-only reviewer headers",
            "caller-supplied tenant ids",
            "Draft Flow",
            "`draft_id`",
            "`candidate_policy_version`",
            "`etag`",
            "docs/policy/schema.md",
            "Validate Flow",
            "junas.policy.load_policy_profile",
            "production validation enabled",
            "`validation_status`",
            "`policy_version`",
            "policy_config_validation_failed",
            "Publish Flow",
            "expected active `policy_id` plus `policy_version`",
            "Rollback Flow",
            "prior published version",
            "Audit Journal Events",
            "policy_config_draft_created",
            "policy_config_validated",
            "policy_config_published",
            "policy_config_rolled_back",
            "changed field names",
            "No policy engine in frontend code",
            "No raw reviewed content or matched spans",
        ):
            self.assertIn(token, text)

    def test_admin_console_reviewer_queue_requirements(self):
        text = (ROOT / "docs" / "admin-console" / "reviewer-queue.md").read_text(
            encoding="utf-8"
        )
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        requirements = (ROOT / "docs" / "admin-console" / "requirements.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("admin-console/reviewer-queue.md", docs_index)
        self.assertIn("docs/admin-console/reviewer-queue.md", requirements)
        for token in (
            "Reviewer Queue Requirements",
            "`approval_required` decisions",
            "`request_approval` actions",
            "assignment",
            "rationale",
            "SLA",
            "immutable audit trail requirement",
            "HMAC-chained tamper-evidence only",
            "`approval_id`",
            "`sla_due_at`",
            "`assigned_to`",
            "`required_reviewer_roles`",
            "Assignment",
            "assign",
            "claim",
            "release",
            "reassign",
            "caller-supplied tenant ids",
            "approval_assigned",
            "approval_reassigned",
            "Rationale",
            "reason_code",
            "docs/policy/journal-replay.md",
            "approval_decision_recorded",
            "SLA timers start at `requested_at`",
            "approval_sla_breached",
            "scripts/verify_journal.py",
            "No broad raw document viewer",
            "No claim that Junas alone provides storage-level immutability",
        ):
            self.assertIn(token, text)

    def test_admin_console_false_positive_triage_requirements(self):
        text = (
            ROOT / "docs" / "admin-console" / "false-positive-triage.md"
        ).read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        requirements = (ROOT / "docs" / "admin-console" / "requirements.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("admin-console/false-positive-triage.md", docs_index)
        self.assertIn("docs/admin-console/false-positive-triage.md", requirements)
        for token in (
            "False-Positive Triage Requirements",
            "authorized reviewer `reject` decisions",
            "detector issue categories",
            "candidate fixture tasks",
            "action=\"reject\"",
            "docs/policy/journal-replay.md",
            "`detector_issue_category`",
            "`context_false_positive`",
            "`defined_term_or_placeholder`",
            "`public_information`",
            "`entity_type_confusion`",
            "`jurisdiction_mismatch`",
            "`span_boundary_error`",
            "`severity_or_policy_mismatch`",
            "`duplicate_or_dedup_error`",
            "create_fixture",
            "file_detector_issue",
            "scripts/generate_legal_fixture.py",
            "scripts/generate_candidate_corpus.py",
            "scripts/check_fixture_scrub.py",
            "scripts/review_candidate_fixture.py",
            "scripts/evaluate_candidate_corpus.py",
            "customer_sample_approved",
            "false_positive_fixture_task_created",
            "false_positive_detector_issue_linked",
            "No automatic detector retraining",
            "No customer text copied into fixtures",
        ):
            self.assertIn(token, text)

    def test_admin_console_audit_export_ui_requirements(self):
        text = (ROOT / "docs" / "admin-console" / "audit-export-ui.md").read_text(
            encoding="utf-8"
        )
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        requirements = (ROOT / "docs" / "admin-console" / "requirements.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("admin-console/audit-export-ui.md", docs_index)
        self.assertIn("docs/admin-console/audit-export-ui.md", requirements)
        for token in (
            "Audit Export UI Requirements",
            "scripts/export_audit_pack.py",
            "scripts/verify_audit_pack.py",
            "scripts/verify_journal.py",
            "Export Request",
            "`reason_code`",
            "`include_defensibility`",
            "`retention_class`",
            "server-chosen output path",
            "Job States",
            "`running_pack_verification`",
            "`verification_failed`",
            "Verification Flow",
            "pack_hmac mismatch",
            "journal chain inconsistent",
            "Pack Sensitivity",
            "controlled evidence",
            "audit_export_requested",
            "audit_export_completed",
            "audit_pack_downloaded",
            "sensitive evidence acknowledgement",
            "No raw-content preview",
            "No export path chosen by the browser client",
            "No download for `reviewer` or `maker` roles",
        ):
            self.assertIn(token, text)

    def test_admin_console_auth_requirements(self):
        text = (ROOT / "docs" / "admin-console" / "auth-requirements.md").read_text(
            encoding="utf-8"
        )
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        requirements = (ROOT / "docs" / "admin-console" / "requirements.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("admin-console/auth-requirements.md", docs_index)
        self.assertIn("docs/admin-console/auth-requirements.md", requirements)
        for token in (
            "Admin Console Auth Requirements",
            "existing Junas tenant identity and roles",
            "API-key registry credentials",
            "JWT credentials",
            "`JUNAS_TENANCY_ENABLED=1`",
            "`JUNAS_TENANCY_AUTH_MODES=api_key`",
            "`X-Tenant-ID`",
            "`X-Actor-Role`",
            "`X-Reviewer-ID`",
            "Local-Dev Header Rule",
            "reject local-dev-only reviewer headers",
            "must never grant admin console access",
            "Role Matrix",
            "Review-session list",
            "Policy config publish/rollback",
            "Audit export request/download",
            "Tenant Isolation",
            "credential-derived tenant",
            "Browser Session Requirements",
            "Auth-Denied Audit Events",
            "admin_dev_header_rejected",
            "admin_local_token_rejected",
            "Missing auth returns 401",
            "Local daemon `X-Junas-Local-Token` cannot authenticate",
        ):
            self.assertIn(token, text)

    def test_admin_console_telemetry_requirements(self):
        text = (
            ROOT / "docs" / "admin-console" / "telemetry-requirements.md"
        ).read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        requirements = (ROOT / "docs" / "admin-console" / "requirements.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("admin-console/telemetry-requirements.md", docs_index)
        self.assertIn("docs/admin-console/telemetry-requirements.md", requirements)
        for token in (
            "Admin Console Telemetry Requirements",
            "policy changes",
            "approval decisions",
            "audit export events",
            "failed access attempts",
            "`schema_version`",
            "`junas.siem.v1`",
            "Common Event Fields",
            "`event_name`",
            "`tenant_id`",
            "Policy Change Events",
            "policy_config_published",
            "policy_config_rolled_back",
            "Approval Decision Events",
            "approval_decision_recorded",
            "decision_recorded",
            "Audit Export Events",
            "audit_export_completed",
            "audit_pack_downloaded",
            "Failed Access Events",
            "admin_dev_header_rejected",
            "admin_local_token_rejected",
            "Aggregations",
            "test/test_siem_export.py",
            "Cross-tenant denials hash object ids",
        ):
            self.assertIn(token, text)

    def test_admin_console_no_build_prototype_exists_before_frontend_dependency(self):
        text = (ROOT / "docs" / "admin-console" / "no-build-prototype.md").read_text(
            encoding="utf-8"
        )
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        requirements = (ROOT / "docs" / "admin-console" / "requirements.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("admin-console/no-build-prototype.md", docs_index)
        self.assertIn("docs/admin-console/no-build-prototype.md", requirements)
        for token in (
            "Admin Console No-Build Prototype",
            "no-build wireframe",
            "before any admin console frontend framework dependency",
            "React, Vue, Svelte, HTMX, Jinja templates",
            "Review Sessions",
            "Reviewer Queue",
            "Policy Config",
            "False-Positive Triage",
            "Audit Exports",
            "Tenant Health",
            "No raw prompt, email body, document text",
            "tenant-scoped pagination",
            "record decision",
            "validate",
            "publish",
            "rollback",
            "create synthetic fixture task",
            "scripts/export_audit_pack.py",
            "scripts/verify_audit_pack.py",
            "scripts/verify_journal.py",
            "Framework Gate",
            "at least five target-user interviews",
            "ADR 0005 is revisited or superseded",
        ):
            self.assertIn(token, text)

    def test_feedback_loop_doc_defines_journal_to_promoted_recall_path(self):
        text = (ROOT / "docs" / "feedback-loop.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("feedback-loop.md", docs_index)
        for token in (
            "Feedback Loop: Journal To Candidate Corpus",
            "There is no automatic journal-to-fixture exporter",
            "Reviewer records a decision in the journal",
            "candidate fixture",
            "promoted recall-lock evidence",
            "scripts/verify_journal.py",
            "scripts/export_audit_pack.py",
            "scripts/verify_audit_pack.py",
            "scripts/generate_legal_fixture.py",
            "scripts/generate_candidate_corpus.py",
            "scripts/check_fixture_scrub.py",
            "scripts/review_candidate_fixture.py",
            "scripts/check_candidate_review_status.py",
            "scripts/reconcile_candidate_strict_labels.py",
            "scripts/promote_candidate_exact_spans.py",
            "scripts/evaluate_candidate_corpus.py",
            "scripts/generate_detector_dashboard.py",
            "scripts/candidate_corpus_report.py",
            "scripts/check_candidate_stage_gate.py",
            "scripts/promote_candidate_fixtures.py",
            "scripts/check_promoted_lock_freshness.py",
            "scripts/check_false_negative_risk.py",
            "scripts/check_precision_risk.py",
            "scripts/run_layer_attribution_eval.py",
            "candidate_recall.lock.json",
            "legal-corpus-reviewed-candidates.lock.json",
            "customer_sample_approved",
            "Do not claim improved detection until",
            "fixture text plus",
            ".labels.json",
            "precision report or precision lock",
            "per-rule override-signal JSON without raw spans",
            "rank rules by override signals",
            "intentionally omits raw matched text",
            "CI runs `scripts/check_promoted_lock_freshness.py`",
            "change to any reviewed-candidate `.txt` or `.labels.json`",
            "both `test/fixtures/legal-corpus-reviewed-candidates/legal-corpus-reviewed-candidates.lock.json`",
            "CI also runs `scripts/check_false_negative_risk.py`",
            "Changes under `src/junas/policy/`, `src/junas/anonymize/`, or `src/junas/backend/`",
            "must pass `scripts/recall_gate.py` against the locked legal corpora",
            "CI also runs `scripts/check_precision_risk.py`",
            "Changes under `src/junas/review/`, `src/junas/backend/`, `src/junas/policy/`",
            "`integrations/outlook_addin/`, or `integrations/browser_extension/`",
            "must pass `scripts/recall_gate.py` against precision-backed locked corpora",
            "No raw journal text copied into fixtures",
            "No promoted accuracy claim from candidate-only",
        ):
            self.assertIn(token, text)

    def test_telemetry_feedback_loop_connects_events_without_raw_content(self):
        text = (ROOT / "docs" / "telemetry-feedback-loop.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        feedback_loop = (ROOT / "docs" / "feedback-loop.md").read_text(encoding="utf-8")

        self.assertIn("telemetry-feedback-loop.md", docs_index)
        self.assertIn("docs/telemetry-feedback-loop.md", feedback_loop)
        for token in (
            "Telemetry Feedback Loop",
            "without storing raw prompts, email bodies, document",
            "`request_id`",
            "`review_id`",
            "`policy_id` / `policy_version`",
            "`surface` / `workflow`",
            "`finding_id` or finding-id hash",
            "`document_hash`",
            "`idempotency_key_hash`",
            "`adapter_review_started`",
            "`review_started`",
            "`adapter_policy_outcome_received`",
            "`approval_requested`",
            "`decision_recorded`",
            "`adapter_completion_recorded`",
            "warning override rate by surface and policy version",
            "raw prompts",
            "email subject or body text",
            "matched spans or `matched_text`",
            "recipient addresses",
            "auth header values",
            "docs/policy/decision-contract.md",
            "docs/admin-console/telemetry-requirements.md",
            "test/test_siem_export.py",
        ):
            self.assertIn(token, text)

    def test_decision_taxonomy_doc_defines_allowed_feedback_labels(self):
        text = (ROOT / "docs" / "policy" / "decision-taxonomy.md").read_text(
            encoding="utf-8"
        )
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        journal_replay = (ROOT / "docs" / "policy" / "journal-replay.md").read_text(
            encoding="utf-8"
        )
        feedback_loop = (ROOT / "docs" / "feedback-loop.md").read_text(encoding="utf-8")

        self.assertIn("policy/decision-taxonomy.md", docs_index)
        self.assertIn("docs/policy/decision-taxonomy.md", journal_replay)
        self.assertIn("docs/policy/decision-taxonomy.md", feedback_loop)
        for token in (
            "Decision Taxonomy",
            "`false_positive`",
            "`false_negative`",
            "`acceptable_risk`",
            "`public_source_confirmed`",
            "`stale_information`",
            "`policy_exception`",
            "orthogonal",
            "review actions",
            "finding id",
            "rule",
            "category",
            "severity",
            "hashes for text-bearing fields",
            "do not require raw prompt",
            "not as automatic training data",
            "DECISION_TAXONOMY",
        ):
            self.assertIn(token, text)

    def test_docs_state_conditional_mapping_and_journal_guarantees(self):
        docs = {
            "README.md": (ROOT / "README.md").read_text(encoding="utf-8"),
            "mapping-store-hardening.md": (ROOT / "docs" / "mapping-store-hardening.md").read_text(
                encoding="utf-8"
            ),
            "threat-model.md": (ROOT / "docs" / "threat-model.md").read_text(encoding="utf-8"),
            "admin-security.md": (ROOT / "docs" / "admin-security.md").read_text(encoding="utf-8"),
            "statutory-coverage.md": (ROOT / "docs" / "statutory-coverage.md").read_text(
                encoding="utf-8"
            ),
            "subject-erasure.md": (ROOT / "docs" / "security" / "subject-erasure.md").read_text(
                encoding="utf-8"
            ),
            "journal-replay.md": (ROOT / "docs" / "policy" / "journal-replay.md").read_text(
                encoding="utf-8"
            ),
        }
        all_doc_paths = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
        all_docs = "\n".join(path.read_text(encoding="utf-8") for path in all_doc_paths)

        for path in ("mapping-store-hardening.md", "threat-model.md", "admin-security.md"):
            text = docs[path]
            self.assertIn("JUNAS_MAPPING_STORE_KEY", text)
            self.assertIn("JUNAS_JOURNAL_KEY", text)
            self.assertIn("JUNAS_JOURNAL_KEYS_FILE", text)
        for token in (
            "key-gated mapping encryption",
            "persisted mapping files are not application-encrypted",
            "Fernet-encrypted only when `JUNAS_MAPPING_STORE_KEY` is supplied",
            "tamper-evident only when `JUNAS_JOURNAL_KEY` or",
            "does not provide OS-level append-only storage",
            "OS/filesystem layer is not append-only",
            "Conditional mapping-store encryption",
            "Conditional HMAC-chained review journal integrity",
            "With configured journal keys",
        ):
            self.assertIn(token, all_docs)
        for forbidden in (
            "Encrypted local mapping store (Fernet, key-gated)",
            "encrypted mappings, HMAC journal chain",
            "The review journal is append-only",
            "remain append-only",
            "Append-only journals",
            "immutable review-session findings",
            "immutable journaled review sessions",
            "immutable journals",
            "HMAC journal and audit-pack export provide tamper-evident",
        ):
            self.assertNotIn(forbidden, all_docs)

    def test_data_retention_matrix_covers_required_artifacts(self):
        text = (ROOT / "docs" / "security" / "data-retention.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("security/data-retention.md", docs_index)
        for token in (
            "`journal`",
            "`mapping_store`",
            "`subject_index`",
            "`review_sessions`",
            "`matter_terms`",
            "`adapter_telemetry`",
            "`siem`",
            "`audit_packs`",
            "`fixtures`",
            "`reports`",
            "scripts/check_retention_manifest.py",
            "scripts/erase_subject.py",
            "scripts/check_fixture_scrub.py",
        ):
            self.assertIn(token, text)

    def test_feedback_artifact_retention_policy_covers_hashes_labels_sidecars_erasure(self):
        text = (ROOT / "docs" / "security" / "feedback-artifact-retention.md").read_text(
            encoding="utf-8"
        )
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        retention = (ROOT / "docs" / "security" / "data-retention.md").read_text(
            encoding="utf-8"
        )
        feedback = (ROOT / "docs" / "feedback-loop.md").read_text(encoding="utf-8")

        self.assertIn("security/feedback-artifact-retention.md", docs_index)
        self.assertIn("docs/security/feedback-artifact-retention.md", retention)
        self.assertIn("docs/security/feedback-artifact-retention.md", feedback)
        for token in (
            "Feedback Artifact Retention",
            "hashes such as `document_hash`, `pii_hash`, finding-id hashes",
            "candidate and reviewed `.labels.json` files",
            "fixture task `.sidecar.json` files and reviewed `.bucket.json` sidecars",
            "raw customer samples approved for reproduction work",
            "Legal hold",
            "Subject erasure behavior",
            "Raw Sample Admission",
            "`customer_sample_approved` evidence exists",
            "retention class and expiry",
            "subject-erasure disposition",
            "scripts/erase_subject.py",
            "subject_erasure_recorded",
            "Regenerate fixtures, labels, locks, reports, and dashboards",
            "source flag: `synthetic`, `scrubbed_customer_sample`, or `hash_only_signal`",
            "legal-hold status",
            "scrub/check evidence before commit",
        ):
            self.assertIn(token, text)

    def test_install_admin_threat_and_limitations_docs_cover_lastbit_controls(self):
        install = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
        admin = (ROOT / "docs" / "admin-security.md").read_text(encoding="utf-8")
        threat = (ROOT / "docs" / "threat-model.md").read_text(encoding="utf-8")
        limitations = (ROOT / "docs" / "known-limitations.md").read_text(encoding="utf-8")
        combined = "\n".join([install, admin, threat, limitations])

        for token in (
            "codesign",
            "notarytool",
            "auto-start",
            "Update:",
            "Uninstall:",
            "Okta",
            "Microsoft Entra ID",
            "SAML",
            "External KMS",
            "customer-held",
            "SIEM",
            "redacted",
            "not legal advice",
            "procurement-grade",
            "threat",
            "Known Limitations",
        ):
            self.assertIn(token, combined)

    def test_known_limitations_cover_office_browser_vendor_platform_limits(self):
        text = (ROOT / "docs" / "known-limitations.md").read_text(encoding="utf-8")

        for token in (
            "Microsoft 365/Office.js platform support",
            "tenant admin assignment",
            "client version",
            "requirement sets",
            "Outlook Smart Alerts `SoftBlock` is not fail-closed",
            "Word taskpane is user-triggered review",
            "Chrome/Edge MV3 behavior",
            "managed profile policy",
            "DOM selectors",
            "CSP",
            "frames",
            "shadow DOM",
            "mobile apps",
            "native apps",
            "unmanaged browsers",
            "universal capture",
            "universal DLP",
            "full-browser DLP",
            "guaranteed tenant-wide enforcement",
            "workflow activation layers",
        ):
            self.assertIn(token, text)

    def test_procurement_faq_links_only_promoted_accuracy_evidence(self):
        text = (ROOT / "docs" / "faq" / "procurement.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("faq/procurement.md", docs_index)
        for token in (
            "# Procurement FAQ",
            "## Accuracy Claim Rule",
            "docs/accuracy.md",
            "test/fixtures/legal-corpus-reviewed-candidates/legal-corpus-reviewed-candidates.lock.json",
            "reports/layer-attribution/20260608-strict-item70v2_strict_candidate_eval.json",
            "docs/candidate_corpus_status.md",
            "Before claiming improved detection",
            "fixture text plus `.labels.json`",
            "the promoted recall lock was",
            "precision evidence is committed",
            "`docs/accuracy.md` was regenerated",
            "1,428 approved legal/cross-jurisdiction documents",
            "17,552 strict expected labels",
            "strict recall `1.0000`",
            "strict precision `0.9269`",
            "not an independent market benchmark",
            "No Junas score on TAB or ai4privacy is claimed",
            "Do not use screenshots, demo flows, unpromoted candidate sidecars",
            "Run a customer pilot validation corpus",
            "false positives",
            "false negatives",
            "docs/product/non-goals.md",
            "docs/known-limitations.md",
        ):
            self.assertIn(token, text)
        for forbidden in (
            "best-in-class",
            "industry-leading",
            "production-ready",
            "guaranteed accuracy",
            "zero false negatives",
            "complete coverage",
        ):
            self.assertNotIn(forbidden, text.lower())

    def test_operator_faq_explains_junas_complements_dlp(self):
        text = (ROOT / "docs" / "faq" / "operator.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("faq/operator.md", docs_index)
        for token in (
            "# Operator FAQ",
            "Checked on 2026-07-01",
            "pre-send review",
            "safe rewrite",
            "audit-evidence layer",
            "enterprise control plane",
            "Microsoft Purview DLP",
            "https://learn.microsoft.com/en-us/purview/dlp-learn-about-dlp",
            "Enterprise applications and devices",
            "Inline web traffic",
            "Google Workspace DLP",
            "https://knowledge.workspace.google.com/admin/security/about-dlp",
            "My Drive and Shared drives",
            "Chat DLP",
            "Slack DLP",
            "https://slack.com/help/articles/12914005852819-Slack-data-loss-prevention",
            "messages, text-based files, and canvases",
            "unsupported content types",
            "Endpoint Controls",
            "MDM",
            "EDR",
            "SIEM export",
            "Do not disable existing DLP",
            "sole exfiltration control",
            "docs/product/non-goals.md",
            "docs/known-limitations.md",
            "docs/security/adapter-threat-model.md",
        ):
            self.assertIn(token, text)

    def test_developer_faq_explains_endpoint_choice(self):
        text = (ROOT / "docs" / "faq" / "developer.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("faq/developer.md", docs_index)
        for token in (
            "# Developer FAQ",
            "Call `POST /review` first",
            "`policy_decision`",
            "`action_catalog`",
            "`review_id`",
            "`review_expires_at`",
            "Use `POST /pseudonymize`",
            "restore the original text later through `POST /reidentify`",
            "Use `POST /anonymize`",
            "not proof of statistical anonymization",
            "Use `POST /redact`",
            "no original matched text",
            "Use `POST /redact-pii`",
            "Use `POST /safe-rewrite`",
            "Use `POST /reidentify` only after `/pseudonymize`",
            "Use `POST /documents/scrub`",
            "not a replacement for `/review`",
            "Use `POST /classify` or `POST /classify/batch` only for legacy clients",
            "Endpoint Choice Table",
            "`POST /hold-until-public`",
            "`POST /cite-public-source`",
            "`POST /request-approval` then `POST /review/{review_id}/decision`",
            "docs/schema.md",
            "docs/api/versioning.md",
            "docs/policy/decision-contract.md",
            "docs/api/python_client.md",
        ):
            self.assertIn(token, text)

    def test_redactor_to_review_migration_guide_covers_policy_pivot(self):
        text = (ROOT / "docs" / "migration" / "redactor-to-review.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("migration/redactor-to-review.md", docs_index)
        for token in (
            "# Redactor-To-Review Migration Guide",
            "pre-send review boundary",
            "call `/review`",
            "`policy_decision`",
            "`action_catalog`",
            "`review_id`",
            "`review_expires_at`",
            "top-level `send_allowed` is compatibility",
            "`/pseudonymize` is for reversible placeholder workflows",
            "`/anonymize` is irreversible placeholder output",
            "`/redact-pii`",
            "`/safe-rewrite`",
            "`/request-approval`",
            "Inventory clients that call `/classify`, `/pseudonymize`, `/anonymize`, or `/redact`",
            "Require a fresh `/review`",
            "`/classify` and `/classify/batch` remain compatibility shims",
            "`/v1` aliases are not exposed yet",
            "Review before send/share/submit",
            "A transformation endpoint is the policy decision",
            "docs/faq/developer.md",
            "docs/policy/decision-contract.md",
        ):
            self.assertIn(token, text)

    def test_install_doc_separates_server_desktop_and_adapter_deployments(self):
        text = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
        headings = (
            "## Server Install",
            "## Local Offline Desktop Install",
            "## Outlook Add-In Deployment",
            "## Browser Extension Deployment",
            "## Word Taskpane Deployment",
        )

        for heading in headings:
            self.assertIn(heading, text)
        heading_offsets = [text.index(heading) for heading in headings]
        self.assertEqual(heading_offsets, sorted(heading_offsets))
        for token in (
            "uv sync --extra dev",
            "./scripts/launch/run_prod.sh",
            "docker compose up --build",
            "uv sync --extra local --extra packaging",
            "./scripts/package_macos_desktop.sh",
            "packaging/macos/install.sh",
            "junas-local",
            "integrations/outlook_addin/manifest.xml",
            "scripts/render_outlook_manifest.py",
            "scripts/validate_outlook_manifest.py",
            "docs/integrations/outlook.md",
            "integrations/browser_extension/",
            "./scripts/package_browser_extension.sh",
            "docs/integrations/genai-browser.md",
            "integrations/word_addin/manifest.xml",
            "docs/integrations/word.md",
        ):
            self.assertIn(token, text)

    def test_running_doc_is_backend_only_and_links_adapter_launch_docs(self):
        text = (ROOT / "docs" / "running.md").read_text(encoding="utf-8")

        self.assertIn("## Backend Launch", text)
        self.assertIn("./scripts/launch/run_backend_only.sh", text)
        self.assertIn("These launchers start the FastAPI backend only", text)
        self.assertIn("## Adapter Launches", text)
        for link in (
            "docs/integrations/direct-api.md",
            "docs/integrations/outlook.md",
            "docs/integrations/genai-browser.md",
            "docs/integrations/word.md",
            "docs/integrations/desktop-watcher.md",
            "docs/integrations/dms.md",
        ):
            self.assertIn(link, text)
        launch_section = text[text.index("## Backend Launch") : text.index("## Docker")]
        self.assertNotIn("junas-watch", launch_section)
        self.assertNotIn("package_browser_extension.sh", launch_section)
        self.assertNotIn("manifest.xml", launch_section)

        for path in (
            ROOT / "docs" / "integrations" / "direct-api.md",
            ROOT / "docs" / "integrations" / "outlook.md",
            ROOT / "docs" / "integrations" / "genai-browser.md",
            ROOT / "docs" / "integrations" / "word.md",
            ROOT / "docs" / "integrations" / "dms.md",
        ):
            self.assertIn("./scripts/launch/run_backend_only.sh", path.read_text(encoding="utf-8"))

    def test_distribution_artifacts_exist_for_packaging_surfaces(self):
        expected = [
            ROOT / "scripts" / "package_macos_desktop.sh",
            ROOT / "scripts" / "package_browser_extension.sh",
            ROOT / "packaging" / "macos" / "com.junas.local.plist.template",
            ROOT / "packaging" / "macos" / "install.sh",
            ROOT / "packaging" / "macos" / "update.sh",
            ROOT / "packaging" / "macos" / "uninstall.sh",
            ROOT / "packaging" / "windows" / "README.md",
            ROOT / "integrations" / "browser_extension" / "manifest.json",
            ROOT / "integrations" / "outlook_addin" / "manifest.xml",
            ROOT / "integrations" / "word_addin" / "manifest.xml",
            ROOT / "integrations" / "word_addin" / "taskpane.js",
            ROOT / "integrations" / "desktop" / "watch.py",
            ROOT / "test" / "fixtures" / "outlook_smart_alert_messages.json",
        ]
        for path in expected:
            self.assertTrue(path.exists(), f"missing {path}")

        macos_packager = (ROOT / "scripts" / "package_macos_desktop.sh").read_text(encoding="utf-8")
        extension_packager = (ROOT / "scripts" / "package_browser_extension.sh").read_text(encoding="utf-8")
        launchd = (ROOT / "packaging" / "macos" / "com.junas.local.plist.template").read_text(encoding="utf-8")
        word_manifest = (ROOT / "integrations" / "word_addin" / "manifest.xml").read_text(encoding="utf-8")
        word_js = (ROOT / "integrations" / "word_addin" / "taskpane.js").read_text(encoding="utf-8")

        self.assertIn("codesign", macos_packager)
        self.assertIn("notarytool", macos_packager)
        self.assertIn("stapler", macos_packager)
        self.assertIn("integrations/browser_extension", extension_packager)
        self.assertIn("--pack-extension", extension_packager)
        self.assertIn("RunAtLoad", launchd)
        outlook_manifest = (ROOT / "integrations" / "outlook_addin" / "manifest.xml").read_text(encoding="utf-8")
        self.assertIn("{{JUNAS_OUTLOOK_ADDIN_ORIGIN}}", outlook_manifest)
        self.assertIn('Host Name="Document"', word_manifest)
        self.assertIn("/review", word_js)
        self.assertIn("X-Junas-Local-Token", word_js)
        self.assertIn('degraded_policy: "warn"', word_js)
        self.assertIn("degraded_modes", word_js)
        self.assertIn("send_allowed", word_js)

    def test_desktop_watcher_is_not_in_readme_quick_start(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        quick_start = re.search(r"## Quick Start(?P<body>.*?)## What Junas Does", readme, re.S)
        fallback = re.search(r"## Experimental Local Fallback(?P<body>.*?)## API Surface", readme, re.S)
        packaging = re.search(r"## Packaging & Deployment(?P<body>.*?)## Screenshots", readme, re.S)

        self.assertIsNotNone(quick_start)
        self.assertIsNotNone(fallback)
        self.assertIsNotNone(packaging)
        self.assertNotIn("junas-watch", quick_start.group("body"))
        self.assertNotIn("--clipboard", quick_start.group("body"))
        self.assertNotIn("packaging/macos/install.sh", quick_start.group("body"))
        self.assertIn("junas-watch", fallback.group("body"))
        self.assertIn("console script remains installed", fallback.group("body"))
        self.assertIn("experimental-local-fallback", fallback.group("body"))
        self.assertIn("desktop-watcher.md", fallback.group("body"))
        self.assertIn("Optional admin-controlled LaunchAgent lifecycle", packaging.group("body"))
        self.assertIn("not a default developer quickstart", packaging.group("body"))
        self.assertIn('junas-watch = "junas.desktop.watch:main"', pyproject)
        self.assertIn("experimental-local-fallback console script", pyproject)

    def test_root_integrations_index_names_supported_and_future_surfaces(self):
        text = (ROOT / "INTEGRATIONS.md").read_text(encoding="utf-8")
        for token in (
            "Direct API",
            "Outlook Smart Alerts",
            "Browser GenAI extension",
            "Word taskpane",
            "Desktop watcher",
            "DMS hooks",
            "Future Slack",
            "Future Google Workspace",
            "docs/integrations/maturity-matrix.md",
        ):
            self.assertIn(token, text)

    def test_dependency_scanning_doc_covers_release_surfaces(self):
        text = (ROOT / "docs" / "security" / "dependency-scanning.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("security/dependency-scanning.md", docs_index)
        for token in (
            "uv export --locked --all-extras",
            "uvx pip-audit -r reports/security/requirements-all.txt",
            "integrations/browser_extension/manifest.json",
            "npm audit --audit-level=high",
            "scripts/render_outlook_manifest.py",
            "scripts/validate_outlook_manifest.py",
            "integrations/word_addin/",
            "uv export --locked --extra packaging",
            "uv run pyinstaller packaging/junas-local.spec",
            "reports/security/junas-local.sha256",
            "GitHub Dependency Review",
            "https://pypa.github.io/pip-audit/",
            "https://docs.npmjs.com/cli/v11/commands/npm-audit",
        ):
            self.assertIn(token, text)

    def test_release_checklist_covers_required_security_gates(self):
        text = (ROOT / "docs" / "security" / "release-checklist.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("security/release-checklist.md", docs_index)
        for token in (
            "test/test_openapi_snapshot.py",
            "scripts/export_openapi_examples.py",
            "test/test_api_auth.py",
            "test/test_tenant_isolation.py",
            "test/test_backend_log_privacy.py",
            "test/test_siem_export.py",
            "scripts/check_fixture_scrub.py",
            "test/test_local_daemon_acl.py",
            "scripts/smoke_local_daemon_acl.py",
            "X-Junas-Local-Token",
            "test/test_frontend_integration.py",
            "test/test_browser_extension.py",
            "Office Runtime storage",
            "scripts/generate_sbom.py --target all",
            "docs/security/dependency-scanning.md",
            "docs/security/sbom.md",
            "--require-desktop-artifact",
        ):
            self.assertIn(token, text)

    def test_direct_api_integration_doc_covers_baseline_contract(self):
        text = (ROOT / "docs" / "integrations" / "direct-api.md").read_text(encoding="utf-8")
        for token in (
            "Maturity: `core`",
            "POST /review",
            '"surface": "api"',
            '"workflow": "api_review"',
            "policy_decision",
            "Idempotency-Key",
            "/safe-rewrite",
            "/request-approval",
            "docs/policy/decision-contract.md",
        ):
            self.assertIn(token, text)

    def test_adapter_protocol_doc_defines_shared_contract(self):
        text = (ROOT / "docs" / "integrations" / "adapter-protocol.md").read_text(encoding="utf-8")
        integrations_index = (ROOT / "docs" / "integrations" / "README.md").read_text(encoding="utf-8")

        self.assertIn("adapter-protocol.md", integrations_index)
        for token in (
            "Status: normative for adapters",
            "## Request Contract",
            "`text` or `document_base64`",
            "`document_filename` and `document_mime_type`",
            "`source_jurisdiction`",
            "`destination_jurisdiction`",
            "`document_type`",
            "`review_profile`",
            "`degraded_policy`",
            "`surface`",
            "`workflow`",
            "`actor_role`",
            "`recipient_domains`",
            "`recipient_count`",
            "`attachment_count`",
            "`sensitivity_label`",
            "`external_destination`",
            "`requested_action`",
            "`session_id`",
            'surface="outlook"',
            'workflow="email_send"',
            'surface="browser_genai"',
            'workflow="prompt_submit"',
            "## Response Contract",
            "`policy_decision.decision`",
            "`policy_decision.required_actions`",
            "`policy_decision.recommended_actions`",
            "`policy_decision.blocking_findings`",
            "`review_expires_at`",
            "`action_catalog`",
            "## Auth Headers",
            "`Authorization: Bearer <jwt-or-api-token>`",
            "`X-API-Key: <key>`",
            "`X-Junas-Local-Token: <token>`",
            "`Idempotency-Key: <opaque-key>`",
            "Tenant identity comes from validated credentials",
            "## Retry Semantics",
            "Transport timeout or network error",
            "HTTP 429 or 503",
            "HTTP 400 or Pydantic validation error",
            "HTTP 401 or 403",
            "Malformed JSON or missing `policy_decision`",
            "## Timeouts",
            "Outlook Smart Alerts",
            "Browser GenAI submit",
            "DMS upload/check-in",
            "## Idempotency Keys",
            "content_hmac",
            "adapter_attempt_epoch",
            "## Telemetry Events",
            "Allowed fields",
            "Prohibited fields",
            "`idempotency_key_hash`",
            "outlook_review_started",
            "browser_policy_decision_received",
            "dms_review_started",
            "api_review_started",
            "raw prompt, email body, document text",
            "matched text, rewritten text",
        ):
            self.assertIn(token, text)

    def test_failure_semantics_doc_defines_adapter_degradation_modes(self):
        text = (ROOT / "docs" / "integrations" / "failure-semantics.md").read_text(encoding="utf-8")
        integrations_index = (ROOT / "docs" / "integrations" / "README.md").read_text(encoding="utf-8")

        self.assertIn("failure-semantics.md", integrations_index)
        for token in (
            "Status: normative for adapter behavior",
            "## Failure Classes",
            "Transport failure",
            "Auth failure",
            "Malformed response",
            "Backend degraded review",
            "Adapter context failure",
            "Platform bypass",
            "## Completion Modes",
            "`allow-on-failure`",
            "`soft-block-on-failure`",
            "`hard-block-on-failure`",
            "`admin-configured-degradation`",
            "Failure mode is separate from policy decision",
            "## Backend Degradation",
            "`degraded_policy`",
            "`allow`",
            "`warn`",
            "`block_send`",
            "`required_actions=[\"retry_review\"]`",
            "## Surface Defaults",
            "Outlook Smart Alerts send",
            "Add-in unavailable before event execution follows Outlook `SoftBlock`",
            "Browser GenAI submit",
            "Selector failure means no policy decision was evaluated",
            "DMS upload/check-in",
            "Direct API",
            "Word taskpane",
            "Desktop watcher",
            "## Admin Configuration",
            "`failure_mode`",
            "`timeout_ms`",
            "`retry_budget`",
            "`break_glass_roles`",
            "`allowed_failure_classes`",
            "`telemetry_required`",
            "Admins must not configure user-controlled fields to weaken failure behavior",
            "## Retry And Break-Glass",
            "Do not convert malformed response into allow",
            "adapters are not approval authorities",
            "## Telemetry",
            "`failure_class`",
            "`failure_mode`",
            "`idempotency_key_hash`",
            "raw prompt, email body, document text",
            "auth headers, JWTs, API keys",
            "## Minimum QA",
            "backend timeout",
            "HTTP 401/403 auth failure",
            "valid response without `policy_decision`",
            "valid response with `degraded_modes`",
            "platform unavailable path",
        ):
            self.assertIn(token, text)

    def test_adapter_auth_doc_defines_tenant_credential_boundary(self):
        text = (ROOT / "docs" / "integrations" / "auth.md").read_text(encoding="utf-8")
        integrations_index = (ROOT / "docs" / "integrations" / "README.md").read_text(encoding="utf-8")

        self.assertIn("auth.md", integrations_index)
        for token in (
            "Status: normative for adapters",
            "## Supported Modes",
            "API key registry",
            "`X-API-Key: <key>`",
            "JWT",
            "`Authorization: Bearer <jwt>`",
            "Local daemon pairing",
            "`X-Junas-Local-Token: <signed-token>`",
            "## API Key Registry",
            "JUNAS_TENANCY_ENABLED=1",
            "JUNAS_TENANCY_AUTH_MODES=api_key",
            "JUNAS_TENANT_CREDENTIALS_JSON",
            "Resolves `tenant_id`, `subject`, and `roles`",
            "## JWT",
            "JUNAS_JWT_ISSUER",
            "JUNAS_JWT_AUDIENCE",
            "JUNAS_JWT_JWKS_URL",
            "JUNAS_JWT_TENANT_CLAIM",
            "Validates signature, issuer, audience, expiry",
            "SAML deployments should terminate SAML",
            "## Local Daemon Pairing",
            "POST /local/pairing/start",
            "POST /local/pairing/approve",
            "POST /local/pairing/claim",
            "Pairing request TTL: 300 seconds",
            "Signed local client token TTL: 90 days",
            "Origin` matches `JUNAS_LOCAL_DAEMON_ALLOWED_ORIGINS`",
            "## Tenant Context",
            "Tenant context is derived only from validated credentials",
            "Caller-supplied tenant ids are ignored",
            "`X-Tenant-ID`",
            "`tenant_id`",
            "Tenant A reading Tenant B review sessions",
            "Reidentify calls crossing tenant mapping stores",
            "Approval or decision writes against another tenant's journal",
            "## Route Auth Expectations",
            "`/review/{review_id}/decision`",
            "`/reidentify`",
            "Do not retry 401 or 403 automatically",
            "## Telemetry Boundary",
            "`auth_mode`",
            "`tenant_hash`",
            "API keys, JWTs, local tokens",
        ):
            self.assertIn(token, text)

    def test_adapter_privacy_doc_defines_collection_and_storage_boundary(self):
        text = (ROOT / "docs" / "integrations" / "privacy.md").read_text(encoding="utf-8")
        integrations_index = (ROOT / "docs" / "integrations" / "README.md").read_text(encoding="utf-8")

        self.assertIn("privacy.md", integrations_index)
        for token in (
            "Status: normative for adapters",
            "## Collection Boundary",
            "Raw text",
            "Memory only until review/rewrite response is handled",
            "`document_base64`",
            "Matched text",
            "Workflow context",
            "Auth material",
            "Adapters must not scrape unrelated page content",
            "## Data Movement",
            "Hosted backend",
            "Raw content leaves the user device or SaaS hook",
            "Local daemon",
            "stays on the endpoint",
            "Direct API",
            "DMS hook",
            "Audit-grade optional helpers",
            "must not silently switch raw content from local daemon to hosted server",
            "## Allowed Storage",
            "idempotency key hash, not raw key",
            "Adapters must not persist",
            "raw prompt, email body, subject, document text",
            "matched text, rewritten text, replacement text",
            "recipient addresses, attachment filenames",
            "## Surface Rules",
            "Outlook",
            "Browser GenAI",
            "DMS",
            "Direct API",
            "Word",
            "Desktop watcher",
            "## Telemetry Boundary",
            "Allowed telemetry fields",
            "Prohibited telemetry fields",
            "## Training And Feedback",
            "Customer text is not training data by default",
            "training, fine-tuning, distillation",
            "docs/security/feedback-artifact-retention.md",
            "## Privacy QA",
            "browser local storage",
            "extension storage",
            "Office runtime storage",
            "console logs",
            "local daemon mode does not call hosted backend without explicit configuration",
            "hosted server mode uses HTTPS",
            "failed review, timeout, malformed response",
        ):
            self.assertIn(token, text)

    def test_adapter_telemetry_doc_defines_events_fields_and_siem_mapping(self):
        text = (ROOT / "docs" / "integrations" / "telemetry.md").read_text(encoding="utf-8")
        integrations_index = (ROOT / "docs" / "integrations" / "README.md").read_text(encoding="utf-8")

        self.assertIn("telemetry.md", integrations_index)
        for token in (
            "Status: normative for adapters",
            "## Schemas",
            "`junas.outlook.telemetry.v1`",
            "`junas.browser.telemetry.v1`",
            "`junas.dms.telemetry.v1`",
            "`junas.api.telemetry.v1`",
            "`junas.siem.v1`",
            "## Event Names",
            "outlook_review_started",
            "outlook_policy_decision_received",
            "outlook_user_proceeded_after_warning",
            "outlook_user_blocked",
            "outlook_user_requested_approval",
            "outlook_backend_failure",
            "browser_prompt_review_started",
            "browser_policy_decision_received",
            "browser_user_canceled",
            "browser_user_rewrote",
            "browser_user_proceeded_after_warning",
            "browser_selector_failure",
            "browser_backend_timeout",
            "dms_review_started",
            "dms_policy_decision_received",
            "dms_upload_held",
            "dms_upload_blocked",
            "dms_backend_failure",
            "api_review_started",
            "api_policy_decision_received",
            "api_backend_failure",
            "## Allowed Fields",
            "`schema_version`",
            "`event_name`",
            "`failure_class`",
            "`tenant_hash`",
            "`idempotency_key_hash`",
            "`matter_id_hash`",
            "## Prohibited Fields",
            "raw prompt, email body, subject, document text",
            "matched text, rewritten text, replacement text",
            "auth headers, API keys, JWTs",
            "## SIEM Mapping",
            "`event_type=\"adapter_telemetry\"`",
            "`category=\"audit\"`",
            "`category=\"security\"`",
            "`category=\"privacy\"`",
            "`outcome` such as `started`, `succeeded`, `blocked`",
            "`src/junas/backend/siem.py` sensitive-key rules",
            "## Required Event Fields",
            "`*_review_started`",
            "`*_policy_decision_received`",
            "`*_backend_failure`",
            "## Aggregations",
            "warning override rate by surface and policy version",
            "Unsafe aggregations",
            "top recipient addresses",
            "## QA",
            "globalThis.junasTelemetrySink(event)",
            "DOM `junas:telemetry` events",
            "sanitize_details",
        ):
            self.assertIn(token, text)

    def test_dms_integration_doc_covers_upload_metadata_failure_and_audit_fields(self):
        text = (ROOT / "docs" / "integrations" / "dms.md").read_text(encoding="utf-8")
        for token in (
            "Maturity: `experimental`",
            'surface="dms"',
            'workflow="document_upload"',
            "Required Metadata",
            "Failure Behavior",
            "Audit Fields To Store",
            "matter_id",
            "document_id",
            "Idempotency-Key",
            "policy_decision.decision",
            "text_hash",
        ):
            self.assertIn(token, text)

    def test_genai_browser_doc_covers_target_assumptions_without_universal_claim(self):
        text = (ROOT / "docs" / "integrations" / "genai-browser.md").read_text(encoding="utf-8")
        for token in (
            "chatgpt.com",
            "claude.ai",
            "gemini.google.com",
            "Generic textarea",
            "textarea",
            "contenteditable",
            "not universal browser DLP",
            "do not guarantee",
            "Target DOM mismatch",
            'surface="browser_genai"',
            'workflow="prompt_submit"',
            "browser-enterprise-deployment.md",
            "test/test_browser_extension_playwright.py",
            "Telemetry Events",
            "Activation Layer Boundaries",
            "activation layer",
            "coverage guarantee",
            "Mobile apps",
            "native desktop apps",
            "Mobile browser sessions",
            "Unrecognized web UIs",
            "no capture",
            "not as a clean verdict",
            "sole enterprise",
            "Chrome content scripts",
            "Manual QA Matrix",
            "Chrome managed",
            "Chrome unmanaged",
            "Edge managed",
            "Edge unmanaged",
            "`local_daemon`",
            "`hosted_server`",
            "offline mode",
            "chrome://policy",
            "edge://policy",
            "blocked hosts do not read clipboard or call backend",
            "submit is not silently allowed after failed review",
            "Adapter Domain Policy",
            "allowedInspectionHosts",
            "blockedInspectionHosts",
            "Blocked hosts win",
            "cannot expand",
            "runtime_allowed_hosts",
            "runtime_blocked_hosts",
            "Chrome extension match patterns",
            "Microsoft Edge extension match patterns",
            "junas.browser.telemetry.v1",
            "browser_prompt_review_started",
            "browser_policy_decision_received",
            "browser_user_canceled",
            "browser_user_rewrote",
            "browser_user_proceeded_after_warning",
            "browser_selector_failure",
            "browser_backend_timeout",
            "globalThis.junasTelemetrySink(event)",
            "must not include raw prompt text",
        ):
            self.assertIn(token, text)

    def test_browser_enterprise_deployment_doc_covers_chrome_edge_policy(self):
        text = (ROOT / "docs" / "integrations" / "browser-enterprise-deployment.md").read_text(
            encoding="utf-8"
        )
        integrations_index = (ROOT / "docs" / "integrations" / "README.md").read_text(encoding="utf-8")
        browser = (ROOT / "docs" / "integrations" / "browser-extension.md").read_text(encoding="utf-8")

        self.assertIn("browser-enterprise-deployment.md", integrations_index)
        self.assertIn("browser-enterprise-deployment.md", browser)
        for token in (
            "Checked on 2026-07-01",
            "ExtensionInstallForcelist",
            "ExtensionSettings",
            "https://chromeenterprise.google/policies/extension-install-forcelist/",
            "https://support.google.com/chrome/a/answer/9867568",
            "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/extensioninstallforcelist",
            "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/extensionsettings",
            "https://clients2.google.com/service/update2/crx",
            "https://edge.microsoft.com/extensionwebstorebase/v1/crx",
            "update manifest XML",
            "override_update_url",
            "Chrome Web Store",
            "Edge Add-ons",
            "Microsoft Entra ID",
            "MDM",
            "JUNAS_CHROME_EXTENSION_KEY",
            "chrome://policy",
            "edge://policy",
            "chrome://extensions",
            "edge://extensions",
            "not production deployment evidence",
            "no raw prompt text",
            "Do not treat a force-installed extension as fail-closed enforcement",
        ):
            self.assertIn(token, text)

    def test_outlook_doc_covers_smart_alerts_deployment_fallback_and_limits(self):
        text = (ROOT / "docs" / "integrations" / "outlook.md").read_text(encoding="utf-8")
        for token in (
            "Smart Alerts Flow",
            "SendMode=\"SoftBlock\"",
            "surface=\"outlook\"",
            "workflow=\"email_send\"",
            "Admin Deployment",
            "Tenant Deployment Guide",
            "Exchange admin",
            "Application Administrator",
            "Microsoft Entra ID",
            "Settings > Integrated apps",
            "Deploy Add-in",
            "Specific users/groups",
            "Just me",
            "top-level Microsoft Entra groups",
            "dynamic groups",
            "security groups",
            "up to 24 hours",
            "up to 72 hours",
            "Client Compatibility Notes",
            "Outlook on the web",
            "new Outlook on Windows",
            "classic Outlook on Windows",
            "Version 2206 (Build 15330.20196)",
            "Simple MAPI send coverage",
            "Version 2301 (Build 17126.20004)",
            "Outlook on Mac",
            "Version 16.65 (22082700)",
            "Outlook mobile for iOS/Android",
            "Not an enforcement target",
            "QA Checklist",
            "Internal recipient",
            "External recipient",
            "No attachment",
            "Attachment present",
            "PII body",
            "MNPI body",
            "Timeout",
            "Backend unavailable",
            "attachment_count=0",
            "attachment_count>0",
            "Junas local review is unavailable",
            "Telemetry Events",
            "junas.outlook.telemetry.v1",
            "outlook_review_started",
            "outlook_policy_decision_received",
            "outlook_user_proceeded_after_warning",
            "outlook_user_blocked",
            "outlook_user_requested_approval",
            "outlook_backend_failure",
            "globalThis.junasTelemetrySink(event)",
            "There is no backend transport endpoint",
            "must not include raw body",
            "Privacy Check",
            "does not write message body",
            "browser local storage",
            "Office runtime storage",
            "console logs",
            "render_outlook_manifest.py",
            "validate_outlook_manifest.py",
            "Event Runtime Bundle",
            "launchevent.js",
            "Do not add ES module",
            "CORS And Well-Known URI Checklist",
            ".well-known/microsoft-officeaddins-allowed.json",
            "JSRuntime.Url",
            "OPTIONS",
            "X-Junas-Local-Token",
            "Microsoft 365 admin-managed deployment",
            "Fallback Behavior",
            "Failure-Mode Table",
            "Add-in unavailable before event runs",
            "Backend timeout or unavailable",
            "Offline mode / Work Offline",
            "Malformed response",
            "Auth failure",
            "Degraded document extraction",
            "not a fail-closed enforcement path",
            "Known Client Limitations",
            "Mailbox requirement set 1.15",
            "Simple MAPI",
        ):
            self.assertIn(token, text)

    def test_sequence_diagrams_doc_covers_outlook_smart_alerts_review(self):
        text = (ROOT / "docs" / "integrations" / "sequence-diagrams.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        integrations_index = (ROOT / "docs" / "integrations" / "README.md").read_text(encoding="utf-8")
        outlook = (ROOT / "docs" / "integrations" / "outlook.md").read_text(encoding="utf-8")

        self.assertIn("integrations/sequence-diagrams.md", docs_index)
        self.assertIn("sequence-diagrams.md", integrations_index)
        self.assertIn("sequence-diagrams.md#outlook-smart-alerts-send-review", outlook)
        for token in (
            "## Outlook Smart Alerts Send Review",
            "OnMessageSend event",
            "POST /review",
            'surface="outlook"',
            'workflow="email_send"',
            "policy_decision",
            "event.completed({allowEvent: true})",
            "sendModeOverride: promptUser",
            "approval_required",
            "Smart Alert blocks current send attempt",
            "no message body",
            "matched text",
        ):
            self.assertIn(token, text)

    def test_sequence_diagrams_doc_covers_browser_prompt_safe_rewrite(self):
        text = (ROOT / "docs" / "integrations" / "sequence-diagrams.md").read_text(encoding="utf-8")
        browser = (ROOT / "docs" / "integrations" / "genai-browser.md").read_text(encoding="utf-8")

        self.assertIn("sequence-diagrams.md#browser-genai-prompt-review-and-safe-rewrite", browser)
        for token in (
            "## Browser GenAI Prompt Review And Safe Rewrite",
            "Resolve prompt composer and submit control",
            "POST /review",
            'surface="browser_genai"',
            'workflow="prompt_submit"',
            "policy_decision",
            "Prompt user to proceed or cancel",
            "rewrite_required and safe_rewrite offered",
            "POST /safe-rewrite",
            "rewritten_text",
            "Replace composer text with rewritten_text",
            "must not silently block submit",
            "must not save prompt text",
            "extension storage",
            "console logs",
        ):
            self.assertIn(token, text)

    def test_sequence_diagrams_doc_covers_dms_upload_review(self):
        text = (ROOT / "docs" / "integrations" / "sequence-diagrams.md").read_text(encoding="utf-8")
        dms = (ROOT / "docs" / "integrations" / "dms.md").read_text(encoding="utf-8")

        self.assertIn("sequence-diagrams.md#dms-upload-check-in-review", dms)
        for token in (
            "## DMS Upload Check-In Review",
            "Upload or check in document",
            "document_id",
            "matter_id",
            "POST /review",
            'surface="dms"',
            'workflow="document_upload"',
            "policy_decision",
            "Store review id, decision, actions, policy version",
            "Permit check-in and attach audit metadata",
            "Hold version pending reviewer approval",
            "Stop or quarantine check-in",
            "raw document text",
            "matched text",
            "idempotency key hash",
        ):
            self.assertIn(token, text)

    def test_sequence_diagrams_doc_covers_reviewer_approval_retry(self):
        text = (ROOT / "docs" / "integrations" / "sequence-diagrams.md").read_text(encoding="utf-8")
        contract = (ROOT / "docs" / "policy" / "decision-contract.md").read_text(encoding="utf-8")

        self.assertIn("sequence-diagrams.md#reviewer-approval-and-adapter-retry", contract)
        for token in (
            "## Reviewer Approval And Adapter Retry",
            "policy_decision.decision=block or approval_required",
            "POST /request-approval",
            "approval_status=\"pending\"",
            "required_reviewer_roles",
            "POST /review/{review_id}/decision",
            "action=\"approve\"",
            "policy_exception",
            "decision_recorded",
            "GET /review/{review_id}",
            "Replayed findings with latest reviewer decision",
            "Retry workflow completion only when approval satisfies policy",
            "must start a new `/review`",
            "raw prompt, email, document, matched text",
        ):
            self.assertIn(token, text)

    def test_word_doc_marks_taskpane_as_review_not_enforcement(self):
        text = (ROOT / "docs" / "integrations" / "word.md").read_text(encoding="utf-8")
        for token in (
            "Document Review Flow",
            "review selection",
            "review body",
            'document_type="word_document"',
            'degraded_policy="warn"',
            "Enforcement Boundary",
            "not true send-time enforcement",
            "does not block Word save",
            "DMS upload",
            "Failure Behavior",
        ):
            self.assertIn(token, text)

    def test_desktop_watcher_doc_marks_opt_in_local_fallback_not_enforcement(self):
        text = (ROOT / "docs" / "integrations" / "desktop-watcher.md").read_text(encoding="utf-8")
        sample_path = ROOT / "docs" / "integrations" / "desktop-watcher.config.sample.toml"
        sample = tomllib.loads(sample_path.read_text(encoding="utf-8"))
        for token in (
            "Opt-In Local Fallback Flow",
            "junas-watch --watch-folder",
            "junas-watch --clipboard",
            "`junas-watch` remains a packaged console script",
            "Maturity: `experimental-local-fallback`",
            "Intended Use",
            "offline local fallback",
            "demos",
            "power users",
            "Do not use it as enterprise",
            "endpoint DLP",
            "Enforced production workflows",
            "Optional LaunchAgent Install",
            "optional and admin-controlled",
            "not a default developer quickstart path",
            "RunAtLoad",
            "KeepAlive",
            "Clipboard polling is never enabled by default",
            "desktop-watcher.config.sample.toml",
            "flag/env based",
            "clipboard = false",
            "requires explicit user opt-in",
            "Threat Model",
            "Clipboard sensitivity",
            "pbpaste",
            "Local token use",
            "JUNAS_LOCAL_DAEMON_TOKEN",
            "Notifications",
            "osascript",
            "Watched-folder scope",
            "dedicated drop directory",
            "Accidental large-file scans",
            "no max-file-size option",
            "Folder Watch",
            "Clipboard Watch",
            "not enterprise endpoint enforcement",
            "does not block paste",
            "cannot prove that every local file",
        ):
            self.assertIn(token, text)

        self.assertEqual(sample["schema"], "junas.desktop_watcher.config.sample.v1")
        self.assertEqual(sample["maturity"], "experimental-local-fallback")
        self.assertEqual(sample["backend"]["base_url"], "http://127.0.0.1:8765")
        self.assertEqual(sample["sources"]["watch_folder"], "./drop")
        self.assertEqual(sample["sources"]["clipboard"], False)
        self.assertEqual(sample["output"]["notify"], False)
        self.assertEqual(sample["operator_ack"]["clipboard_requires_explicit_opt_in"], True)
        self.assertEqual(sample["operator_ack"]["dedicated_watch_folder_required"], True)

        threat_model = (ROOT / "docs" / "security" / "adapter-threat-model.md").read_text(encoding="utf-8")
        packaging = (ROOT / "packaging" / "README.md").read_text(encoding="utf-8")
        for token in (
            "notification path exposure",
            "broad recursive folder scans",
            "accidental large-file scans",
            "count/path-only notifications",
            "dedicated watched folder",
        ):
            self.assertIn(token, threat_model)
        for token in (
            "Optional LaunchAgent lifecycle",
            "admin-controlled",
            "not a developer quickstart",
            "starts at login",
            "developer smoke tests",
        ):
            self.assertIn(token, packaging)


if __name__ == "__main__":
    unittest.main()
