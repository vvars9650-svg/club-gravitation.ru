"""Fail-closed runtime configuration for isolated TEST and PROD contours."""

import os

from .legal_text import CONSENT_TEXT_SHA256, verify_frozen_consent
from .repository import RepositoryUnavailable


ALLOWED_ENVIRONMENTS = frozenset(("TEST", "PROD"))


def runtime_environment():
    environment = os.getenv("V5_ENVIRONMENT", "TEST")
    if environment not in ALLOWED_ENVIRONMENTS:
        raise RepositoryUnavailable("invalid_runtime_environment")
    return environment


def runtime_settings():
    environment = runtime_environment()
    prefix = "V5_PROD" if environment == "PROD" else "V5_TEST"
    endpoint = os.getenv(f"{prefix}_YDB_ENDPOINT") or (os.getenv("YDB_ENDPOINT") if environment == "TEST" else None)
    database = os.getenv(f"{prefix}_YDB_DATABASE") or (os.getenv("YDB_DATABASE") if environment == "TEST" else None)
    bucket = os.getenv(f"{prefix}_PHOTO_BUCKET")
    consent_hash = os.getenv(f"{prefix}_CONSENT_TEXT_HASH")

    if not all((endpoint, database, bucket, consent_hash)):
        raise RepositoryUnavailable(f"missing_{environment.lower()}_configuration")
    if environment == "TEST":
        if not consent_hash.startswith("TEST-"):
            raise RepositoryUnavailable("consent_hash_must_be_test_marked")
    else:
        # PROD may only use the canonical frozen legal baseline, never a test or
        # caller-supplied placeholder hash.
        if consent_hash != CONSENT_TEXT_SHA256 or consent_hash.startswith("TEST-"):
            raise RepositoryUnavailable("invalid_prod_consent_hash")
        try:
            verify_frozen_consent()
        except ValueError as exc:
            raise RepositoryUnavailable("frozen_consent_hash_mismatch") from exc
    return {
        "environment": environment,
        "endpoint": endpoint,
        "database": database,
        "bucket": bucket,
        "consent_hash": consent_hash,
    }
