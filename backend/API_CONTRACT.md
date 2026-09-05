# API contract — GRAVITATION V3

Status: working production contract for backend migration.

## POST /applications

Primary content type: `application/json`.

Compatibility parsing for `application/x-www-form-urlencoded` remains during migration, but the V3 frontend must use JSON.

### Required request header

`Idempotency-Key: <16-128 chars>`

Allowed characters: latin letters, digits, `.`, `_`, `:`, `-`.

The same key must be reused when the browser retries the same submission. An edited/new submission receives a new key.

### Required fields

- `full_name`
- `age`
- `gender`
- `city`
- `phone`
- `photo_data`
- `pd_consent`
- `rules_accepted`

### Optional fields

- `visit_krasnodar`
- `telegram`
- `vk`
- `instagram`
- `email`
- `preferred_contact`
- `occupation`
- `life_outside_work`
- `interests`
- `relationship_context`
- `desired_connections`
- `values_in_people`
- `barriers_to_meeting`
- `source`
- `what_interested`
- `event_expectations`
- `successful_evening`
- `return_reason`
- `social_comfort`
- `initiative`
- `acquaintance_scenario`
- `unacceptable_behavior`
- `convenient_days`
- `comfortable_price`
- `contact_consent`
- `application_channel`
- `page_url`
- `utm_source`
- `utm_medium`
- `utm_campaign`
- `utm_content`
- `utm_term`
- `referrer`
- `user_agent`
- `client_timestamp`
- `website` (honeypot, must stay empty)

## Legacy V2 aliases accepted by backend

- `name` → `full_name`
- `city_visit` → `visit_krasnodar`
- `life_beyond_work` → `life_outside_work`
- `interest_reason` → `what_interested`
- `expectations` → `event_expectations`
- `connection_goal` → `desired_connections`
- `values_people` → `values_in_people`
- `meeting_barriers` → `barriers_to_meeting`
- `introduction_scenario` → `acquaintance_scenario`
- `personal_data_consent` → `pd_consent`
- `rules_consent` → `rules_accepted`
- `submitted_at_client` → `client_timestamp`

The final V3 frontend should send canonical names directly.

## Normalization

Backend is authoritative for validation and normalization.

- Russian phone numbers are normalized to `+7XXXXXXXXXX` when possible.
- Email is trimmed and lower-cased.
- Telegram is normalized to lower-case `@username`; `t.me/...` is accepted.

## Participant resolution

Phone is the authoritative identity key because it is mandatory for an application.

A dedicated YDB table `participant_phone_keys` has `phone` as its primary key and maps each normalized phone to exactly one `participant_id`. This replaces the unsupported attempt to add a UNIQUE secondary index to the existing `participants` table.

Resolution rules:

1. if the submitted phone exists in `participant_phone_keys`, that participant is reused;
2. email and Telegram may confirm the same participant;
3. if email or Telegram points to a different participant, backend returns HTTP `409 participant_conflict`;
4. if a new phone matches email/Telegram of an existing participant, backend does not silently change the phone and returns `409 participant_conflict` for manual review;
5. if no contact points to an existing participant, a new Participant is created and its phone key is inserted in the same YDB write transaction.

The primary key on `participant_phone_keys.phone` is the database-level concurrency guard. Two simultaneous first applications with the same phone cannot create two canonical phone owners. A losing concurrent request retries against the winner.

Repeat applications do not reset lifecycle fields such as status, priority, owner, next action or original `created_at`. Empty optional contact fields do not erase existing non-empty values.

## Idempotency

`application_id`, consent IDs, file ID and audit ID are deterministically derived from `Idempotency-Key`.

The backend stores an idempotency fingerprint in `applications.raw_payload`, based on the normalized request and photo hash.

- first accepted request: HTTP `201`;
- exact retry with same key and payload: HTTP `200`, `idempotent_replay: true`, no duplicate Application/Consent/File/Audit rows;
- same key with different payload: HTTP `409 idempotency_conflict`.

## Photo storage

Photo is validated server-side as JPG, PNG or WEBP and limited to 1.5 MB after browser processing.

The Yandex Disk path is derived from `application_id` plus the request fingerprint, not from `participant_id`. This prevents a concurrent changed payload using the same idempotency key from overwriting the photo accepted for another payload, and it also avoids moving files when a concurrent phone claim resolves to another participant.

If the configured Yandex Disk access token returns `401`, backend uses refresh token/client credentials from Lockbox to obtain a fresh access token for the running function instance.

## Success responses

First creation, HTTP `201`:

```json
{
  "success": true,
  "message": "Заявка принята",
  "participant_id": "GR-...",
  "application_id": "APP-...",
  "file_id": "FILE-...",
  "participant_reused": false,
  "idempotent_replay": false,
  "request_id": "..."
}
```

Idempotent replay, HTTP `200`:

```json
{
  "success": true,
  "message": "Заявка принята",
  "participant_id": "GR-...",
  "application_id": "APP-...",
  "file_id": "FILE-...",
  "participant_reused": true,
  "idempotent_replay": true,
  "request_id": "..."
}
```

## Errors

- `400 validation_error` — invalid request;
- `405 method_not_allowed` — wrong HTTP method;
- `409 participant_conflict` — contacts require manual review;
- `409 idempotency_conflict` — same idempotency key with changed payload;
- `413 payload_too_large` — request too large;
- `502 storage_error` — Yandex Disk failure;
- `500 internal_error` — unexpected backend failure.

## Request tracing

Every real backend response contains `request_id` in JSON and `X-Request-Id` response header. Logs contain technical identifiers and error classes, not full application payloads, phone numbers, emails, OAuth tokens or photos.
