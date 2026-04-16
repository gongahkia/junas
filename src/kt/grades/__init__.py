"""Grade conversion between Font, V-scale, YDS, and UIAA.

Canonical form is a V-scale integer in [0, 17]. Conversions are approximate
(indicative, per theCrag and common climbing references) and intentionally
single-valued per V-grade — there is no universally agreed one-to-one mapping.
"""

from kt.grades.tables import (
    SYSTEMS,
    convert,
    parse_to_v,
    system_value,
    v_to_font,
    v_to_uiaa,
    v_to_yds,
)

__all__ = [
    "SYSTEMS",
    "convert",
    "parse_to_v",
    "system_value",
    "v_to_font",
    "v_to_uiaa",
    "v_to_yds",
]
