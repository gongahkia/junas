import pytest

from test.test_sensitivity import review


@pytest.mark.parametrize(
    "text",
    [
        (
            "Orchid Estuary Ltd. — Board paper\n\nThe issuer signed a binding agreement to acquire "
            "all issued shares.\n\nNeither the agreement nor the offer price has been publicly "
            "disclosed. The signed deal is material."
        ),
        (
            "Orchid Estuary Ltd. published an investor update. Since publication, its largest "
            "customer terminated its contract. The termination is price-sensitive and has not been "
            "publicly disclosed."
        ),
        (
            "Orchid Estuary Ltd. publicly announced unchanged guidance. After publication, the "
            "issuer received a termination notice on a contract accounting for 32% of annual "
            "revenue. Neither the notice nor revised forecast has been publicly disclosed."
        ),
        (
            "Orchid Estuary Ltd.\n\nThe issuer received an acceleration notice. The notice is "
            "expected to materially affect its share price. Neither party has disclosed the notice "
            "publicly."
        ),
        (
            "Orchid Estuary Ltd. signed a takeover agreement at a 25% premium to the last closing "
            "price. The agreement has not been announced on SGXNet or otherwise publicly disclosed."
        ),
    ],
)
def test_linked_event_and_disclosure_assertions(text):
    result = review(text).sensitivity["mnpi"]
    assert result["state"] == "present", result
    assert not result["public_status_verified"]
    for h in result["evidence"]:
        assert text[h["start_char"] : h["end_char"]] == h["matched_text"]
        for c in h["components"]:
            assert h["start_char"] <= c["start_char"] < c["end_char"] <= h["end_char"]
            assert text[c["start_char"] : c["end_char"]] == c["matched_text"]


@pytest.mark.parametrize(
    "text",
    [
        "Orchid Estuary Ltd. has a material acquisition. Birch Terrace Ltd. has not been publicly disclosed.",
        (
            "Orchid Estuary Ltd. has a material acquisition.\n\nThe unrelated service rota has not "
            "been publicly disclosed."
        ),
        (
            "Orchid Estuary Ltd. publicly announced a material acquisition. The acquisition has not"
            " been publicly disclosed."
        ),
        (
            "Orchid Estuary Ltd. signed a material acquisition not yet publicly disclosed, but it "
            "was already publicly announced."
        ),
        ("Hypothetical training example: Orchid Estuary Ltd. signs a material acquisition not yet publicly disclosed."),
        "Orchid Estuary Ltd. has no material acquisition. The acquisition has not been publicly disclosed.",
        "Orchid Estuary Ltd. has an immaterial acquisition that has not been publicly disclosed.",
        "A material acquisition has not been publicly disclosed.",
        (
            "Orchid Estuary Ltd. publicly announced a material acquisition.\n\nAn unpublished "
            "registrar file records a client contact."
        ),
    ],
)
def test_unresolved_or_negative_context_is_not_promoted(text):
    assert review(text).sensitivity["mnpi"]["state"] != "present"


def test_new_named_issuer_does_not_inherit_the_previous_issuer_identity():
    text = (
        "Orchid Estuary Ltd. publicly announced a material acquisition. "
        "Birch Terrace Ltd. has a price-sensitive takeover that has not been publicly disclosed."
    )
    output = review(text).sensitivity["mnpi"]
    assert output["state"] == "present"
    assert all(
        next(c["matched_text"] for c in h["components"] if c["kind"] == "issuer") == "Birch Terrace Ltd"
        for h in output["evidence"]
    )


def test_counterparty_cannot_replace_the_issuer_subject():
    text = (
        "Orchid Estuary Ltd. — Board memorandum\n\nThe issuer received a termination notice "
        "from Birch Terrace Ltd. The contract accounts for 32% of annual revenue. "
        "The termination is price-sensitive and has not been publicly disclosed."
    )
    output = review(text).sensitivity["mnpi"]
    assert output["state"] == "present"
    assert all(
        next(c["matched_text"] for c in h["components"] if c["kind"] == "issuer") == "Orchid Estuary Ltd"
        for h in output["evidence"]
    )


def test_materiality_cannot_be_borrowed_from_a_different_topic():
    text = "Orchid Estuary Ltd. has a material acquisition. The staff rota forecast has not been publicly disclosed."
    assert review(text).sensitivity["mnpi"]["state"] != "present"


def test_abstention_exposes_missing_link_with_source_exact_bounds():
    text = "Orchid Estuary Ltd signed an acquisition. The acquisition has not been publicly disclosed."
    output = review(text).sensitivity["mnpi"]
    assert output["state"] == "unknown"
    assert {d["code"] for d in output["diagnostics"]} == {"missing_materiality"}
    for item in output["diagnostics"]:
        assert text[item["start_char"] : item["end_char"]] == item["matched_text"]


def test_general_guidance_and_routine_correspondence_do_not_inherit_broad_risk_signals():
    for text in [
        "General policy guidance: a listed issuer should assess whether a proposal requires an announcement.",
        "Client name: Anika Moss. The register update concerns a courier contact. Please retain the billing address.",
        (
            "A public consultation does not itself change a listed issuer’s obligations. "
            "The effective date is not confirmed."
        ),
    ]:
        assert review(text).sensitivity["mnpi"]["state"] == "not_detected"
    assert review("Confidential financial amount SGD 50 million.").sensitivity["mnpi"]["state"] == "unknown"


def test_disclosure_cannot_borrow_distant_materiality_within_one_paragraph():
    text = (
        "Orchid Estuary Ltd. signed a material acquisition. "
        + "Routine correspondence remains available. " * 120
        + "The acquisition has not been publicly disclosed."
    )
    assert review(text).sensitivity["mnpi"]["state"] != "present"


def test_repeated_disclosures_keep_evidence_local_and_source_exact():
    from junas.review.contextual_mnpi import contextual_mnpi

    block = "Orchid Estuary Ltd. signed a material acquisition. The acquisition has not been publicly disclosed. "
    text = block * 80
    result = contextual_mnpi(text, [])
    assert result["state"] == "present"
    assert len(result["evidence"]) == 80
    for item in result["evidence"]:
        assert text[item["start_char"] : item["end_char"]] == item["matched_text"]
        assert item["end_char"] - item["start_char"] < 3400
        for component in item["components"]:
            assert text[component["start_char"] : component["end_char"]] == component["matched_text"]


@pytest.mark.parametrize("issuer", ["Alder Estuary Systems Ltd", "Silver Lantern Networks Ltd"])
def test_short_issuer_references_link_to_qualified_anchors_only(issuer):
    alias = " ".join(issuer.split()[:2])
    text = (
        f"Issuer contact at {issuer}.\n\n{alias} received a termination notice from its "
        "largest customer. The contract accounted for 42% of annual revenue. "
        "The termination is price-sensitive and has not been publicly disclosed."
    )
    result = review(text).sensitivity["mnpi"]
    assert result["state"] == "present", result
    subjects = [c for h in result["evidence"] for c in h["components"] if c["kind"] == "issuer"]
    assert any(c["matched_text"] == alias for c in subjects)
    assert all(text[c["start_char"] : c["end_char"]] == c["matched_text"] for c in subjects)


@pytest.mark.parametrize(
    "intro,alias",
    [
        ("Alder Estuary Systems Ltd and Alder Estuary Holdings Ltd", "Alder Estuary"),
        ("Alder Estuary Systems Ltd", "Alder Estuary Networks"),
    ],
)
def test_ambiguous_or_different_company_suffix_cannot_borrow_an_issuer_anchor(intro, alias):
    text = (
        f"Background: {intro}.\n\n{alias} signed a material acquisition. "
        "The agreement is price-sensitive and has not been publicly disclosed."
    )
    assert review(text).sensitivity["mnpi"]["state"] != "present"


def test_board_decision_and_following_materiality_share_one_named_issuer_context():
    text = (
        "Alder Estuary Systems Ltd — listing review\n\n"
        "The board has approved a recall of 21,000 battery packs. "
        "The recall has not been publicly disclosed.\n\n"
        "The disclosure committee considers the decision price-sensitive. "
        "The announcement has not been released."
    )
    result = review(text).sensitivity["mnpi"]
    assert result["state"] == "present", result
    assert any(
        c["matched_text"] == "Alder Estuary Systems Ltd"
        for h in result["evidence"]
        for c in h["components"]
        if c["kind"] == "issuer"
    )


@pytest.mark.parametrize(
    "text",
    [
        "The board approved a price-sensitive recall of 21,000 units that has not been publicly disclosed.",
        (
            "Alder Estuary Ltd and Silver Lantern Ltd.\n\n"
            "The board approved a price-sensitive recall of 21,000 units that has not been publicly disclosed."
        ),
        (
            "Alder Estuary Ltd.\n\nThe board should approve a recall of 21,000 units in a "
            "hypothetical exercise. This is price-sensitive and has not been publicly disclosed."
        ),
        (
            "Alder Estuary Ltd received a termination notice that has not been publicly disclosed.\n\n"
            "Silver Lantern Ltd considers its unrelated decision price-sensitive."
        ),
        (
            "Alder Estuary Ltd received a termination notice that has not been publicly disclosed.\n\n"
            "The decision is price-sensitive and was already publicly announced."
        ),
    ],
)
def test_board_and_forward_materiality_links_require_unambiguous_uncontradicted_context(text):
    assert review(text).sensitivity["mnpi"]["state"] != "present"


@pytest.mark.parametrize("owner", ["the issuer’s", "its", "the"])
@pytest.mark.parametrize("benchmark", ["last", "previous", "prior unaffected"])
def test_price_premium_keeps_possessive_closing_price_link(owner, benchmark):
    text = (
        "Alder Estuary Ltd signed a binding takeover agreement at 32% above "
        f"{owner} {benchmark} closing price. The agreement has not been publicly disclosed."
    )
    assert review(text).sensitivity["mnpi"]["state"] == "present"


def test_no_live_event_denial_is_scoped_to_its_clause():
    negative = (
        "Alder Estuary Ltd — training briefing\n\n"
        "The briefing did not relate to any live defect investigation, stop-sale instruction or recall decision."
    )
    assert review(negative).sensitivity["mnpi"]["state"] == "not_detected"
    positive = negative[:-1] + (
        "; however the board approved a recall of 21,000 battery packs this morning. "
        "The recall is price-sensitive and has not been publicly disclosed."
    )
    assert review(positive).sensitivity["mnpi"]["state"] == "present"


def test_counterparty_field_and_shortened_name_do_not_replace_the_issuer_header():
    text = (
        "Alder Estuary Systems Ltd — issuer\n\nCounterparty: Silver Lantern Holdings Ltd\n\n"
        "The issuer received a termination notice from Silver Lantern. The contract accounted "
        "for 32% of annual revenue. The termination is price-sensitive and has not been publicly disclosed."
    )
    result = review(text).sensitivity["mnpi"]
    assert result["state"] == "present"
    assert all(
        c["matched_text"] == "Alder Estuary Systems Ltd"
        for h in result["evidence"]
        for c in h["components"]
        if c["kind"] == "issuer"
    )


def test_short_name_cannot_borrow_a_distant_qualified_anchor():
    text = (
        "Alder Estuary Systems Ltd. "
        + "Routine correspondence remains available. " * 80
        + "Alder Estuary received a material termination notice that has not been publicly disclosed."
    )
    assert review(text).sensitivity["mnpi"]["state"] != "present"
