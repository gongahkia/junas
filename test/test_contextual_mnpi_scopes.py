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
