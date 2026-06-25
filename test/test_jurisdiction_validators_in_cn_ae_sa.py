"""Items 102 + 103 + 104: validators for IN / CN / AE / SA national-ID + corporate-ID
detectors.

Covers checksum + format validators added to `jurisdictions.py`:
- IN Aadhaar (Verhoeff) — UIDAI 12-digit
- IN PAN — 10-char alphanumeric with entity-type letter
- CN Resident ID — ISO 7064 MOD 11-2 (GB 11643-1999)
- CN USCC — ISO 7064 MOD 31-3 (GB 32100-2015), alphabet excludes I/O/Z/S/V
- AE Emirates ID — format + 784 prefix (checksum not publicly documented)
- KSA National ID + Iqama — format + leading-digit constraint

Known-valid test vectors sourced from public statute / wiki references.
"""

import unittest

from junas.review.jurisdictions import _VALIDATORS


class InAadhaarValidatorTests(unittest.TestCase):
    valid = staticmethod(_VALIDATORS["in_aadhaar"])

    def test_canonical_valid_vector(self):
        # Verhoeff-valid 12-digit Aadhaar sample (UIDAI test vector pattern).
        self.assertTrue(self.valid("234123412346"))

    def test_rejects_zero_leading(self):
        # UIDAI reserves leading 0 + 1; first digit must be 2-9.
        self.assertFalse(self.valid("012345678901"))

    def test_rejects_one_leading(self):
        self.assertFalse(self.valid("123456789012"))

    def test_rejects_all_same_digit(self):
        self.assertFalse(self.valid("999999999999"))
        self.assertFalse(self.valid("222222222222"))

    def test_rejects_short(self):
        self.assertFalse(self.valid("23412341234"))

    def test_rejects_non_digit(self):
        self.assertFalse(self.valid("23412341234X"))

    def test_rejects_mutated_checksum(self):
        # Mutate the final check digit of the canonical valid sample.
        self.assertFalse(self.valid("234123412345"))

    def test_accepts_spaces_and_dashes(self):
        # Verhoeff validates digits only; spacing/punctuation stripped before check.
        self.assertTrue(self.valid("2341 2341 2346"))
        self.assertTrue(self.valid("2341-2341-2346"))


class InPanValidatorTests(unittest.TestCase):
    valid = staticmethod(_VALIDATORS["in_pan"])

    def test_individual_entity_type(self):
        self.assertTrue(self.valid("ABCPK1234A"))

    def test_company_entity_type(self):
        self.assertTrue(self.valid("ABCCK1234A"))

    def test_huf_entity_type(self):
        self.assertTrue(self.valid("ABCHK1234A"))

    def test_trust_entity_type(self):
        self.assertTrue(self.valid("ABCTK1234A"))

    def test_rejects_invalid_entity_type_letter(self):
        # 4th char must be one of PCHFATBLJG; X is not.
        self.assertFalse(self.valid("ABCXK1234A"))

    def test_rejects_wrong_length(self):
        self.assertFalse(self.valid("ABCPK1234"))
        self.assertFalse(self.valid("ABCPK1234AB"))

    def test_rejects_digit_in_letter_slot(self):
        self.assertFalse(self.valid("AB1PK1234A"))

    def test_lowercase_normalized(self):
        self.assertTrue(self.valid("abcpk1234a"))


class CnResidentIdValidatorTests(unittest.TestCase):
    valid = staticmethod(_VALIDATORS["cn_resident_id"])

    def test_wikipedia_canonical_sample(self):
        # Wikipedia Resident Identity Card sample.
        self.assertTrue(self.valid("11010519491231002X"))

    def test_rejects_mutated_checksum(self):
        self.assertFalse(self.valid("110105194912310020"))

    def test_lowercase_x_normalised(self):
        self.assertTrue(self.valid("11010519491231002x"))

    def test_rejects_short(self):
        self.assertFalse(self.valid("110105194912310"))

    def test_rejects_letter_in_body(self):
        self.assertFalse(self.valid("11010519491A31002X"))


class CnUsccValidatorTests(unittest.TestCase):
    valid = staticmethod(_VALIDATORS["cn_uscc"])

    def test_gb32100_canonical_sample(self):
        # GB 32100-2015 canonical-form sample.
        self.assertTrue(self.valid("91350100M000100Y43"))

    def test_rejects_excluded_letter_i(self):
        # USCC alphabet excludes I O Z S V.
        self.assertFalse(self.valid("91350100M000100YI3"))

    def test_rejects_excluded_letter_o(self):
        self.assertFalse(self.valid("9135010OM000100Y43"))

    def test_rejects_wrong_length(self):
        self.assertFalse(self.valid("91350100M000100Y4"))
        self.assertFalse(self.valid("91350100M000100Y433"))

    def test_rejects_mutated_checksum(self):
        # Mutate the final check character.
        self.assertFalse(self.valid("91350100M000100Y44"))


class AeEmiratesIdValidatorTests(unittest.TestCase):
    valid = staticmethod(_VALIDATORS["ae_emirates_id"])

    def test_accepts_784_prefix_15_digits(self):
        self.assertTrue(self.valid("784197512345671"))

    def test_accepts_dashed_form(self):
        self.assertTrue(self.valid("784-1975-1234567-1"))

    def test_rejects_non_784_prefix(self):
        self.assertFalse(self.valid("123456789012345"))

    def test_rejects_short(self):
        self.assertFalse(self.valid("78419751234567"))


class SaNationalIdValidatorTests(unittest.TestCase):
    national = staticmethod(_VALIDATORS["sa_national_id"])
    iqama = staticmethod(_VALIDATORS["sa_iqama"])

    def test_national_id_accepts_citizen_prefix_1(self):
        self.assertTrue(self.national("1234567890"))

    def test_national_id_accepts_resident_prefix_2(self):
        self.assertTrue(self.national("2345678901"))

    def test_national_id_rejects_other_prefix(self):
        self.assertFalse(self.national("9234567890"))
        self.assertFalse(self.national("0234567890"))

    def test_iqama_requires_prefix_2(self):
        self.assertTrue(self.iqama("2345678901"))
        self.assertFalse(self.iqama("1234567890"))

    def test_iqama_rejects_wrong_length(self):
        self.assertFalse(self.iqama("234567890"))
        self.assertFalse(self.iqama("23456789012"))


if __name__ == "__main__":
    unittest.main()
