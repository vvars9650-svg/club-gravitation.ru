# API contract — GRAVITATION V3

Status: working contract for backend migration.

## POST /applications

Content-Type: `application/json`

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

## Participant resolution

Before a new `Participant` is created, the backend searches existing participants by exact submitted contacts:

1. phone;
2. email when present;
3. Telegram when present.

If exactly one participant matches, that `participant_id` is reused and a new `Application` is linked to it.

If submitted contacts point to more than one existing participant, the backend must not merge records automatically and returns HTTP `409` with code `participant_conflict` for manual review.

A repeat application must not reset lifecycle fields such as status, priority, owner, next action or original `created_at` of an existing participant.

### Success response

HTTP 201

```json
{
  "success": true,
  "message": "Заявка принята",
  "participant_id": "GR-...",
  "application_id": "APP-...",
  "file_id": "FILE-...",
  "participant_reused": false
}
```

`participant_reused` is `true` when the application is linked to an already existing participant.

### Contact conflict

HTTP 409

```json
{
  "success": false,
  "error": "Контактные данные требуют ручной проверки",
  "code": "participant_conflict"
}
```

### Other errors

```json
{
  "success": false,
  "error": "..."
}
```

This contract is intentionally separated from the current V2 HTML field names. The V3 frontend adapter will map form field names to this API contract before switching production from Google Apps Script to Yandex API Gateway.
