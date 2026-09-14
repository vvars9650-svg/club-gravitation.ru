# V5 application contract

`POST /applications` is TEST-only and accepts `application/json` and `Idempotency-Key`.

The canonical payload uses internal `form_version: "FORM-2.2"` and legal versions
`PPD-2.1` / `CONSENT-PD-2.1`. Both `policy_acknowledged: true` and
`personal_data_consent: true` are independently required. These version identifiers
must not be displayed in public form copy.

Canonical multi-value fields are `desired_connections` and
`acquaintance_methods`; both are JSON arrays. The canonical neutral profile field is
`profile_or_messenger_url`. FORM 2.1 legacy fields are not silently accepted.

Photo status is `LEGAL_PRODUCT_BLOCKED_REQUIRED_PHOTO`. No photo field, upload UI,
payload value, or storage integration belongs to Phase A.

The supplied handler remains a TEST-only reference implementation. Live migration,
YDB mutation, deployment, photo handling, and production intake are outside this
contract.
