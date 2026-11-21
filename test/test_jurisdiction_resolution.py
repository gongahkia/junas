"""Jurisdiction admission must not fabricate detector coverage or discard malformed rules."""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from junas import PreSendReviewEngine, ReviewPipeline, classify_text
from junas.cli import main
from junas.review import jurisdictions as j

CODES = ("AE", "AU", "CN", "EU", "HK", "ID", "IN", "JP", "KR", "MY", "PH", "SA", "SEA", "SG", "TH", "UK", "US", "VN")
PACK_DIR = Path(__file__).parents[1] / "src/junas/review/jurisdictions_data"
ALIASES = [
    (alias, raw["code"])
    for path in sorted(PACK_DIR.glob("*.toml"))
    for raw in [tomllib.loads(path.read_text())]
    for alias in raw["aliases"]
]


def _engine(source="SG", destination="SG", text="S1234567D"):
    return PreSendReviewEngine().review(
        text=text,
        source_jurisdiction=source,
        destination_jurisdiction=destination,
        entity_id=None,
        include_suggestions=False,
    )


@pytest.fixture
def custom(monkeypatch, tmp_path):
    monkeypatch.setenv("JUNAS_JURISDICTION_PACKS_DIR", str(tmp_path))
    yield tmp_path
    monkeypatch.delenv("JUNAS_JURISDICTION_PACKS_DIR")
    j.reload_registry()


def _pack(path, *, code="XY", aliases=("SYNTHETIC REGION",), extra=""):
    path.write_text(
        f"code = {json.dumps(code)}\n"
        'label = "Synthetic policy"\n'
        'pii_rules = ["LOCAL_PII_POLICY"]\n'
        'mnpi_rules = ["LOCAL_MNPI_POLICY"]\n'
        'references = ["Synthetic internal policy"]\n'
        f"aliases = {json.dumps(list(aliases))}\n" + extra
    )


def _recognizer(**changes):
    item = dict(
        name="synthetic token",
        rule_name="synthetic_token",
        pattern=r"CODE: (ZX\d{4})",
        severity="high",
        capture_group=1,
        reason="synthetic identifier",
    )
    item.update(changes)
    return "\n[[recognizers]]\n" + "\n".join(f"{k} = {json.dumps(v)}" for k, v in item.items()) + "\n"


@pytest.mark.parametrize("code", CODES)
def test_each_supported_canonical_code_retains_generic_detection(code):
    result = _engine(code, code, "Contact person@example.test")
    assert result.jurisdictions_applied == [code]
    assert "email_address" in {f.rule for f in result.findings}
    assert not result.degraded_modes


@pytest.mark.parametrize("alias,code", ALIASES)
def test_existing_aliases_case_and_whitespace(alias, code):
    result = _engine("  " + alias.lower() + "\t", code, "Contact person@example.test")
    assert result.jurisdictions_applied == [code]
    for f in result.findings:
        assert f.metadata["source_jurisdiction"] == code
        assert f.metadata["destination_jurisdiction"] == code


def test_default_and_explicit_sg_are_identical():
    default = ReviewPipeline().review_text("S1234567D").to_dict()
    explicit = (
        ReviewPipeline().review_text("S1234567D", source_jurisdiction="SG", destination_jurisdiction="SG").to_dict()
    )
    assert default == explicit
    assert default["jurisdictions_applied"] == ["SG"]
    assert default["overall_risk"] == "HIGH_RISK"


@pytest.mark.parametrize("value", ["SNGAPORE", "ZZ", "GENERIC", "", "   ", 0, False, [], {}])
@pytest.mark.parametrize("role", ["source", "destination"])
def test_invalid_identifiers_are_rejected_instead_of_synthesizing_packs(value, role):
    source, destination = (value, "SG") if role == "source" else ("SG", value)
    with pytest.raises(ValueError, match="jurisdiction"):
        j.resolve_rule_packs(source, destination)
    with pytest.raises(ValueError, match="jurisdiction"):
        _engine(source, destination)


@pytest.mark.parametrize("source,dest", [("SNGAPORE", None), ("US", "SNGAPORE"), ("SG", ""), ("SG", False)])
def test_pipeline_refuses_before_extraction_or_ocr(source, dest):
    with patch("junas.pipeline.extract_review_document") as extract:
        with pytest.raises(ValueError, match="jurisdiction"):
            ReviewPipeline().review_text("S1234567D", source_jurisdiction=source, destination_jurisdiction=dest)
        extract.assert_not_called()


def test_library_convenience_function_propagates_resolution_failure():
    with pytest.raises(ValueError, match="SNGAPORE"):
        classify_text("S1234567D", source_jurisdiction="SNGAPORE")


@pytest.mark.parametrize("option", ["--source-jurisdiction", "--destination-jurisdiction"])
def test_cli_unknown_identifier_returns_two_without_safe_output(option, capsys):
    assert main(["classify", "--text", "S1234567D", option, "SNGAPORE"]) == 2
    out = capsys.readouterr()
    assert not out.out
    assert "SNGAPORE" in out.err and "jurisdiction" in out.err


def test_source_destination_union_and_attribution_remain_strictest_wins():
    for source, destination in [("US", "SINGAPORE"), ("SINGAPORE", "USA")]:
        result = _engine(source, destination)
        assert "sg_nric_fin" in {f.rule for f in result.findings}
        assert result.overall_risk.value == "HIGH_RISK"
        assert set(result.jurisdictions_applied) == {"SG", "US"}
        f = next(f for f in result.findings if f.rule == "sg_nric_fin")
        assert f.metadata["jurisdiction_policy"] == "strictest_wins"
        assert f.metadata["rule_jurisdictions"] == ["SG"]
        assert f.metadata["source_jurisdiction"] == ("US" if source == "US" else "SG")
        assert f.metadata["destination_jurisdiction"] == ("SG" if destination == "SINGAPORE" else "US")


def test_explicit_regional_baseline_pack_is_not_unknown_fallback():
    result = _engine("ASEAN", "SEA", "Contact person@example.test")
    assert result.jurisdictions_applied == ["SEA"]
    assert not result.degraded_modes
    with pytest.raises(ValueError):
        _engine("GENERIC", "GENERIC")


def test_custom_recognizer_and_alias_are_registered(custom):
    _pack(custom / "local.toml", extra=_recognizer())
    j.reload_registry()
    result = _engine("synthetic region", "XY", "CODE: ZX2468")
    assert result.jurisdictions_applied == ["XY"]
    finding = next(f for f in result.findings if f.rule == "synthetic_token")
    assert finding.matched_text == "ZX2468"
    assert finding.legal_basis == "LOCAL_PII_POLICY"
    assert finding.metadata["source_jurisdiction"] == "XY"
    assert "CODE: ZX2468"[finding.start_char : finding.end_char] == finding.matched_text


def test_valid_override_keeps_existing_alias(custom):
    _pack(custom / "override.toml", code="SG", aliases=("INTERNAL SG",))
    j.reload_registry()
    result = _engine("SINGAPORE", "INTERNAL SG")
    assert result.jurisdictions_applied == ["SG"]
    assert any(f.rule == "sg_nric_fin" and f.legal_basis == "LOCAL_PII_POLICY" for f in result.findings)


@pytest.mark.parametrize("extra", ["", "recognizers = []\n"])
def test_optional_recognizers_may_be_absent_for_policy_only_pack(custom, extra):
    _pack(custom / "local.toml", extra=extra)
    j.reload_registry()
    assert j.resolve_rule_packs("XY", "XY")[0].recognizers == ()


@pytest.mark.parametrize(
    "change",
    [
        dict(pattern="["),
        dict(pattern=""),
        dict(name=""),
        dict(rule_name=4),
        dict(severity="critical"),
        dict(validator="typo"),
        dict(capture_group=-1),
        dict(capture_group=2),
        dict(capture_group=True),
        dict(capture_group="1"),
        dict(capture_group=1.5),
        dict(validators="us_ssn"),
    ],
)
def test_malformed_recognizer_refuses_entire_configuration(custom, change):
    _pack(custom / "broken.toml", extra=_recognizer(**change))
    with pytest.raises(ValueError, match="recognizer"):
        j.reload_registry()
    with pytest.raises(ValueError):
        _engine()


@pytest.mark.parametrize(
    "extra",
    [
        'recognizers = "wrong"\n',
        'recognizers = ["wrong"]\n',
        '\n[[recognizers]]\nname = "missing pattern"\nrule_name = "missing"\n',
        "recogniser = []\n",
    ],
)
def test_malformed_or_misspelled_recognizer_container_refuses(custom, extra):
    _pack(custom / "broken.toml", extra=extra)
    with pytest.raises(ValueError):
        j.reload_registry()


@pytest.mark.parametrize(
    "field,value", [("code", ""), ("code", True), ("aliases", "SG"), ("pii_rules", "policy"), ("references", [42])]
)
def test_malformed_pack_field_types_refuse(custom, field, value):
    _pack(custom / "broken.toml")
    path = custom / "broken.toml"
    lines = path.read_text().splitlines()
    path.write_text(
        "\n".join(f"{field} = {json.dumps(value)}" if line.startswith(field + " =") else line for line in lines)
    )
    with pytest.raises(ValueError):
        j.reload_registry()


@pytest.mark.parametrize("alias", ["SG", "SINGAPORE", "USA"])
def test_alias_cannot_redirect_existing_jurisdiction(custom, alias):
    _pack(custom / "collision.toml", aliases=(alias,))
    with pytest.raises(ValueError, match="alias|collision|conflict"):
        j.reload_registry()


def test_custom_canonical_code_cannot_shadow_existing_alias(custom):
    _pack(custom / "collision.toml", code="USA")
    with pytest.raises(ValueError, match="alias|collision|conflict"):
        j.reload_registry()


def test_failed_reload_does_not_leave_old_registry_usable_and_can_recover(custom):
    _pack(custom / "local.toml", extra=_recognizer())
    j.reload_registry()
    assert j.resolve_rule_packs("XY", "XY")
    (custom / "broken.toml").write_text("invalid [")
    with pytest.raises(ValueError):
        j.reload_registry()
    with pytest.raises(ValueError):
        _engine()
    (custom / "broken.toml").unlink()
    j.reload_registry()
    assert j.resolve_rule_packs("XY", "XY")


def test_missing_configured_directory_is_not_silently_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("JUNAS_JURISDICTION_PACKS_DIR", str(tmp_path / "missing"))
    try:
        with pytest.raises(ValueError):
            j.reload_registry()
    finally:
        monkeypatch.delenv("JUNAS_JURISDICTION_PACKS_DIR")
        j.reload_registry()


def test_malformed_configuration_cli_exit_two_not_success(custom):
    (custom / "broken.toml").write_text("invalid [")
    env = {k: v for k, v in os.environ.items() if not k.startswith("JUNAS_")}
    env["JUNAS_JURISDICTION_PACKS_DIR"] = str(custom)
    result = subprocess.run(
        [sys.executable, "-B", "-m", "junas.cli", "classify", "--text", "S1234567D"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert not result.stdout
    assert "broken.toml" in result.stderr
    assert "Traceback" not in result.stderr


def test_configured_nested_capture_group_uses_its_own_occurrence(custom):
    _pack(custom / "local.toml", extra=_recognizer(pattern=r"(AB(ZX\d{4}))", capture_group=2))
    j.reload_registry()
    result = _engine("XY", "XY", "ABZX2468 then ABZX4682")
    findings = [f for f in result.findings if f.rule == "synthetic_token"]
    assert [(f.matched_text, f.start_char, f.end_char) for f in findings] == [("ZX2468", 2, 8), ("ZX4682", 16, 22)]


def test_nonparticipating_capture_group_does_not_fall_back_to_whole_match(custom):
    _pack(custom / "local.toml", extra=_recognizer(pattern=r"(AB)?ZX\d{4}", capture_group=1))
    j.reload_registry()
    result = _engine("XY", "XY", "ZX2468")
    assert not any(f.rule == "synthetic_token" for f in result.findings)
