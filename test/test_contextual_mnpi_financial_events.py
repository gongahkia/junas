"""Authored financial-event variations and controls; exposed development evidence."""

import pytest

from junas.review.contextual_mnpi import contextual_mnpi

FAMILIES = [
    (
        "has deferred payment of its declared dividend. The dividend represents 7% of its last traded share price.",
        "The deferral",
    ),
    (
        "sponsored the pivotal Phase III study that missed its primary efficacy endpoint.",
        "The trial result",
    ),
    (
        "has estimated an impairment. The charge would turn forecast pre-tax profit into a full-year loss.",
        "The expected write-down",
    ),
    (
        "confirmed a missed bond target, triggering a 125-basis-point coupon increase.",
        "The missed target and coupon increase",
    ),
    (
        "approved a correction to its sustainability figures, missing the bond target. "
        "Missing the target would add S$8 million in annual interest, "
        "against last year's S$30 million in pre-tax profit.",
        "The correction and its financing impact",
    ),
]


@pytest.mark.parametrize("issuer", ["Cobalt Estuary Systems Ltd", "Silver Orchard Holdings Ltd"])
@pytest.mark.parametrize("separator", [" ", "\n\n", "\r\n\r\n"])
@pytest.mark.parametrize("event,reference", FAMILIES)
def test_financial_event_families_keep_grounded_links_across_layouts(issuer, separator, event, reference):
    text = f"{issuer} {event}{separator}{reference} has not yet been publicly disclosed."
    result = contextual_mnpi(text, [])
    assert result["state"] == "present", result
    for hypothesis in result["evidence"]:
        assert not hypothesis["public_status_verified"]
        assert {c["kind"] for c in hypothesis["components"]} == {"issuer", "event", "materiality", "claimed_nonpublic"}
        for component in hypothesis["components"]:
            assert text[component["start_char"] : component["end_char"]] == component["matched_text"]


@pytest.mark.parametrize("event,reference", FAMILIES)
def test_public_financial_event_variants_remain_negative(event, reference):
    text = f"Cobalt Estuary Systems Ltd {event} {reference} was publicly announced."
    assert contextual_mnpi(text, [])["state"] == "not_detected"


@pytest.mark.parametrize("event,reference", FAMILIES)
def test_conflicting_public_claims_do_not_become_positive(event, reference):
    text = (
        f"Cobalt Estuary Systems Ltd {event} {reference} was publicly announced. "
        f"{reference} has not yet been publicly disclosed."
    )
    assert contextual_mnpi(text, [])["state"] == "unknown"


@pytest.mark.parametrize(
    "text",
    [
        "Cobalt Estuary Ltd should defer its material dividend. The deferral has not been publicly disclosed.",
        "Cobalt Estuary Ltd might recognise an impairment that would turn profit into a loss. "
        "The impairment has not been publicly disclosed.",
        "Cobalt Estuary Ltd has no material dividend deferral. The deferral has not been publicly disclosed.",
        "Cobalt Estuary Ltd has no impairment. The charge would turn profit into a loss "
        "and has not been publicly disclosed.",
        "Cobalt Estuary Ltd deferred a dividend. The deferral has not been publicly disclosed.",
        "Cobalt Estuary Ltd unblinded a Phase I study that missed its primary endpoint. "
        "The trial result has not been publicly disclosed.",
        "An impairment would turn forecast profit into a loss. It has not yet been publicly disclosed.",
        "Cobalt Estuary Ltd approved a material impairment. Birch Summit Ltd has not disclosed its coupon increase.",
        "Cobalt Estuary Ltd deferred a material dividend. The unrelated staff rota has not been publicly disclosed.",
        "Cobalt Estuary Ltd approved a correction, missing its bond target. Missing the target would add "
        "S$0.01 million in annual interest, against last year's S$90 million in pre-tax profit. "
        "The correction has not been publicly disclosed.",
        "Cobalt Estuary Ltd approved a correction, missing its bond target. Suppose missing the target would add "
        "S$8 million in annual interest, against last year's S$30 million in pre-tax profit. "
        "The correction has not been publicly disclosed.",
        "Cobalt Estuary Ltd approved a correction, missing its bond target. Missing the target would add "
        "S$8 million in annual interest, against last year's USD30 million in pre-tax profit. "
        "The correction has not been publicly disclosed.",
    ],
)
def test_partial_normative_negated_and_unrelated_events_are_not_promoted(text):
    assert contextual_mnpi(text, [])["state"] != "present"


def test_single_token_alias_requires_a_unique_qualified_issuer():
    body = (
        "Cobalt's signed recalculation shows it missed its bond target, triggering a 150-basis-point coupon increase. "
        "The coupon increase has not been publicly disclosed."
    )
    assert contextual_mnpi("Cobalt Estuary Ltd.\n\n" + body, [])["state"] == "present"
    assert contextual_mnpi("Cobalt Estuary Ltd and Cobalt Summit Ltd.\n\n" + body, [])["state"] != "present"


def test_possessive_alias_and_listing_prefix_are_kept_separate():
    text = (
        "Singapore-listed Cobalt Estuary Ltd.\n\n"
        "Cobalt's recalculation confirmed a missed bond target, triggering a 150-basis-point coupon increase. "
        "The coupon increase has not been publicly disclosed."
    )
    output = contextual_mnpi(text, [])
    assert output["state"] == "present", output
    assert any(c["matched_text"] == "Cobalt" for h in output["evidence"] for c in h["components"])
    assert contextual_mnpi(text.replace("Cobalt's", "Singapore's"), [])["state"] != "present"


def test_sponsored_trial_keeps_the_issuer_subject():
    text = (
        "A pivotal Phase III study sponsored by Cobalt Estuary Ltd missed its primary endpoint. "
        "The trial result has not yet been publicly disclosed."
    )
    output = contextual_mnpi(text, [])
    assert output["state"] == "present", output
    assert any(c["matched_text"] == "Cobalt Estuary Ltd" for h in output["evidence"] for c in h["components"])


def test_case_study_correction_retains_the_asserted_past_event():
    text = (
        "Case study erratum: the worksheet should say Cobalt Estuary Ltd's sole bank had cancelled its "
        "credit facility. The cancellation was price-sensitive. "
        "On the case-study date, the cancellation had not been publicly disclosed."
    )
    assert contextual_mnpi(text, [])["state"] == "present"


@pytest.mark.parametrize("event,reference", FAMILIES)
@pytest.mark.parametrize(
    "claim", ["remains unannounced", "has not been made public", "has not been released to the market"]
)
def test_alternative_disclosure_wording_is_linked_and_conflicts_still_abstain(event, reference, claim):
    text = f"Cobalt Estuary Ltd {event} {reference} {claim}."
    assert contextual_mnpi(text, [])["state"] == "present"
    assert contextual_mnpi(text + f" {reference} was released to the market.", [])["state"] == "unknown"


@pytest.mark.parametrize("issuer", ["Cobalt Estuary Ltd", "Méralune Grid Ltd"])
def test_notice_and_impairment_keep_the_same_contract_impact(issuer):
    text = (
        f"{issuer} received a binding termination notice from Birch Summit Ltd. "
        f"The contract accounted for 43% of {issuer}'s revenue. "
        "Neither the notice nor the preliminary impairment estimate has been publicly disclosed."
    )
    output = contextual_mnpi(text, [])
    assert output["state"] == "present", output
    assert all(
        c["matched_text"] == issuer for h in output["evidence"] for c in h["components"] if c["kind"] == "issuer"
    )


def test_financial_period_tags_do_not_turn_aliases_into_different_companies():
    text = (
        "Cobalt Estuary Systems Ltd — issuer memorandum\n\n"
        "Birch Summit Ltd served a notice terminating a contract accounting for 42% of Cobalt's FY2025 revenue. "
        "The termination is price-sensitive and has not been publicly disclosed."
    )
    output = contextual_mnpi(text, [])
    assert output["state"] == "present", output
    assert all(
        c["matched_text"] == "Cobalt" for h in output["evidence"] for c in h["components"] if c["kind"] == "issuer"
    )
    ambiguous = text.replace(
        "42% of Cobalt's FY2025 revenue", "42% of Cobalt's FY2025 revenue and 48% of Birch Summit Ltd's revenue"
    )
    assert contextual_mnpi(ambiguous, [])["state"] == "unknown"
