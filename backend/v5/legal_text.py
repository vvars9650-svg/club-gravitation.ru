"""Canonicalization contract for approved frozen legal source text."""

import hashlib
import unicodedata
from pathlib import Path


CONSENT_TEXT_SHA256 = (
    "7a4ed02773773d680bb56399c943b94e2f35cf97d96b89a29e156d132fca6bf7"
)
FROZEN_CONSENT_2_2_VERIFIED = True


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


def frozen_consent_path():
    return (
        Path(__file__).resolve().parents[2]
        / "legal" / "frozen" / "CONSENT-PD-2.2.txt"
    )


def verify_frozen_consent(path=None):
    source_path = Path(path) if path else frozen_consent_path()
    actual = legal_text_sha256(source_path.read_bytes())
    if actual != CONSENT_TEXT_SHA256:
        raise ValueError("frozen_consent_hash_mismatch")
    return actual
