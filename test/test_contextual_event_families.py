import pytest

from test.test_sensitivity import review


@pytest.mark.parametrize(
    "event",
    [
        "approved an emergency refinancing",
        "received an order suspending its operating licence",
        "decided to withdraw its cash offer",
        "cancelled its bridge loan",
    ],
)
@pytest.mark.parametrize("separator", [" ", "\n\n", "\r\n\r\n"])
def test_actual_events_link_explicit_decisions_and_preserve_components(event, separator):
    text = (
        f"Alder Basin Ltd {event}." + separator + "That price-sensitive decision has not yet been publicly disclosed."
    )
    result = review(text).sensitivity["mnpi"]
    assert result["state"] == "present"
    assert all(
        text[c["start_char"] : c["end_char"]] == c["matched_text"] for e in result["evidence"] for c in e["components"]
    )


@pytest.mark.parametrize("event", ["emergency refinancing", "licence suspension", "withdrawal of the cash offer"])
def test_public_and_hypothetical_event_variants_do_not_become_positive(event):
    for text in [
        f"Alder Basin Ltd publicly announced a material {event}.",
        f"Alder Basin Ltd training example: hypothetical {event}, price-sensitive and not yet publicly disclosed.",
    ]:
        assert review(text).sensitivity["mnpi"]["state"] != "present"


def test_new_events_cannot_cross_an_explicit_different_issuer():
    text = (
        "Alder Basin Ltd approved a material emergency refinancing.\n\n"
        "Different issuer Birch Vale Ltd has not yet publicly disclosed its licence suspension."
    )
    assert review(text).sensitivity["mnpi"]["state"] != "present"
