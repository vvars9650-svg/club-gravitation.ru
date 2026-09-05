# API contract — GRAVITATION V3

Status: working production contract for backend migration.

## POST /applications

Primary content type: `application/json`.

Compatibility parsing for `application/x-www-form-urlencoded` remains in the backend during migration, but the V3 frontend must use JSON.

### Required request header

`Idempotency-Key: <16-128 chars>`

Allowed characters: latin letters, digits, `.`, `_`, `:`, `-`.

The same key must be reused when the browser retries the same submission. A new edited submission must receive a new key.

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

During migration the backend also accepts current V2 field names and maps them internally:

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
- Telegram username is normalized to lower-case `@username` and `t.me/...` is accepted.

## Participant resolution

Before a new `Participant` is created, backend searches existing participants by normalized contacts:

1. phone;
2. email when present;
3. Telegram when present.

If exactly one participant matches, its `participant_id` is reused and a new `Application` is linked to it.

If submitted contacts point to more than one participant, backend returns HTTP `409` with code `participant_conflict` and does not auto-merge records.

A repeat application does not reset lifecycle fields such as status, priority, owner, next action or original `created_at` of an existing participant. Empty optional contact fields do not erase existing non-empty values.

A synchronous unique YDB index on `participants.phone` is a deployment prerequisite for V3.

## Idempotency

`application_id`, consent IDs, file ID and audit ID are deterministically derived from `Idempotency-Key`.

The backend stores an idempotency fingerprint in `applications.raw_payload` based on the normalized request and photo hash.

- First accepted request: HTTP `201`.
- Exact retry with the same key and payload: HTTP `200`, `idempotent_replay: true`, no new Application/Consent/File/Audit rows.
- Same key with a different payload: HTTP `409`, code `idempotency_conflict`.

## Photo storage

Photo is validated server-side as JPG, PNG or WEBP and limited to 1.5 MB after browser processing.

Yandex Disk path includes both `participant_id` and `application_id`, so a new application never overwrites the participant's older photo.

A retry of the same idempotent application may safely overwrite the same application file path.

If the configured Yandex Disk access token returns `401`, backend uses the refresh token/client credentials from Lockbox to obtain a fresh access token for the running function instance.

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

Validation, HTTP `400`:

```json
{
  "success": false,
  "error": "...",
  "code": "validation_error",
  "request_id": "..."
}
```

Contact conflict, HTTP `409`:

```json
{
  "success": false,
  "error": "Контактные данные требуют ручной проверки",
  "code": "participant_conflict",
  "request_id": "..."
}
```

Idempotency conflict, HTTP `409`:

```json
{
  "success": false,
  "error": "Idempotency-Key уже использован для другой заявки",
  "code": "idempotency_conflict",
  "request_id": "..."
}
```

Other statuses used by the backend:

- `405` method not allowed;
- `413` request too large;
- `415` unsupported content type;
- `502` Yandex Disk failure;
- `500` unexpected backend failure.

## Request tracing

Every real backend response contains `request_id` in JSON and `X-Request-Id` response header. Logs contain technical identifiers and error classes, not full application payloads, phone numbers, emails, OAuth tokens or photos.
