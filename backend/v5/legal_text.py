"""Canonicalization contract for approved frozen legal source text."""

import hashlib
import unicodedata
from pathlib import Path


CONSENT_TEXT_SHA256 = (
    "7a4ed02773773d680bb56399c943b94e2f35cf97d96b89a29e156d132fca6bf7"
)
FROZEN_CONSENT_2_2_VERIFIED = True
CURRENT_CONSENT_VERSION = "CONSENT-PD-2.3"
CURRENT_CONSENT_TEXT_SHA256 = "10f8c02d5c034d06c09f80a5f4b67bebbcdc98fcd8d18b4b95718338ac50f8c2"
CONSENT_HASHES = {"CONSENT-PD-2.2": CONSENT_TEXT_SHA256, CURRENT_CONSENT_VERSION: CURRENT_CONSENT_TEXT_SHA256}
CURRENT_DOCUMENT_HASHES = {
    "CONSENT-PD-2.3": CURRENT_CONSENT_TEXT_SHA256,
    "PPD-2.3": "caa57445997081c4df49ff71b346cd1a6ba4282b7408cfbcde0b97d5590d4445",
    "FORM-2.3": "720468a4df6a967f88cd023e5fa0136f93549ef5824114d4710875a5c570d3bb",
}


def canonicalize_legal_text(source):
    """Return canonical UTF-8 bytes without interpreting rendered markup."""
    if not isinstance(source, bytes):
        raise TypeError("legal_source_must_be_bytes")
    text = source.decode("utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    text = unicodedata.normalize(
        "NFC", text.replace("\r\n", "\n").replace("\r", "\n")
    )
    lines = [line.rstrip(" \t") for line in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return ("\n".join(lines) + "\n").encode("utf-8")


def legal_text_sha256(source):
    return hashlib.sha256(canonicalize_legal_text(source)).hexdigest()


def frozen_document_path(version):
    source_path = (
        Path(__file__).resolve().parents[2]
        / "legal" / "frozen" / (version + ".txt")
    )
    if source_path.is_file():
        return source_path
    # The deployment ZIP deliberately contains only the frozen source needed
    # for this integrity check, adjacent to the packaged v5 module.
    return (
        Path(__file__).resolve().parents[1]
        / "legal" / "frozen" / (version + ".txt")
    )


def frozen_consent_path():
    return frozen_document_path("CONSENT-PD-2.2")


def verify_frozen_consent(path=None, version="CONSENT-PD-2.2"):
    source_path = Path(path) if path else frozen_document_path(version)
    actual = legal_text_sha256(source_path.read_bytes())
    if actual != CONSENT_HASHES[version]:
        raise ValueError("frozen_consent_hash_mismatch")
    return actual


def verify_current_documents():
    for version, expected in CURRENT_DOCUMENT_HASHES.items():
        if legal_text_sha256(frozen_document_path(version).read_bytes()) != expected:
            raise ValueError("frozen_legal_hash_mismatch")
    verify_frozen_consent()


def consent_hash_for_version(version, environment="PROD"):
    digest = CONSENT_HASHES[version]
    return "TEST-" + digest if environment == "TEST" else digest
