# V5 application contract

`POST /applications` is TEST-only and accepts `application/json` and `Idempotency-Key`.

The canonical payload uses internal `form_version: "FORM-2.2"` and legal versions
`PPD-2.1` / `CONSENT-PD-2.1`. Both `policy_acknowledged: true` and
`personal_data_consent: true` are independently required. These version identifiers
must not be displayed in public form copy.

Canonical multi-value fields are `desired_connections` and
`acquaintance_methods`; both are JSON arrays. The canonical neutral profile field is
`profile_or_messenger_url`. FORM 2.1 legacy fields are not silently accepted.

Each accepted request creates an immutable Application snapshot. Phone resolution
may link later Applications to the same canonical Participant, but intake never
copies later Application values over that Participant. Broken phone-key linkage is
a deterministic conflict, not a reassignment.

Canonical Participant statuses are `Кандидат`, `Одобрен`, `Не одобрен`, and
`Неактивен`. Processing state remains independently derived from the existing block
flag. Application status and decision are separate concepts.

Photo status is `LEGAL_PRODUCT_BLOCKED_REQUIRED_PHOTO`. No photo field, upload UI,
payload value, matching, or storage integration belongs to Phase A or Phase B.

The supplied handler remains a TEST-only reference implementation. Live migration,
YDB mutation, deployment, photo handling, and production intake are outside this
contract.
