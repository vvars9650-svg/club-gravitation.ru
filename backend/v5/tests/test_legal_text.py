import unittest
from pathlib import Path

from backend.v5.legal_text import (
    CONSENT_TEXT_SHA256,
    FROZEN_CONSENT_2_2_VERIFIED,
    canonicalize_legal_text,
    legal_text_sha256,
    verify_frozen_consent,
)


class LegalTextCanonicalizationTests(unittest.TestCase):
    def test_approved_frozen_consent_has_expected_hash(self):
        self.assertTrue(FROZEN_CONSENT_2_2_VERIFIED)
        self.assertEqual(verify_frozen_consent(), CONSENT_TEXT_SHA256)

    def test_bom_newlines_unicode_and_trailing_whitespace_are_normalized(self):
        variant = "\ufeffCafé  \r\nСтрока\t\r\n\r\n".encode("utf-8")
        expected = "Café\nСтрока\n".encode("utf-8")
        self.assertEqual(canonicalize_legal_text(variant), expected)
        self.assertEqual(legal_text_sha256(variant), legal_text_sha256(expected))

    def test_content_change_changes_hash(self):
        self.assertNotEqual(
            legal_text_sha256(b"approved\n"),
            legal_text_sha256(b"changed\n"),
        )

    def test_invalid_utf8_is_rejected(self):
        with self.assertRaises(UnicodeDecodeError):
            canonicalize_legal_text(b"\xff")

    def test_all_three_frozen_sources_are_present(self):
        frozen = Path(__file__).resolve().parents[3] / "legal" / "frozen"
        for name in ("CONSENT-PD-2.2.txt", "PPD-2.2.txt", "FORM-2.2.txt"):
            self.assertTrue((frozen / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
