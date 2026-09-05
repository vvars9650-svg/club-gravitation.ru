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

### Success response

HTTP 201

```json
{
  "success": true,
  "message": "Заявка принята",
  "participant_id": "GR-...",
  "application_id": "APP-...",
  "file_id": "FILE-..."
}
```

### Error response

```json
{
  "success": false,
  "error": "..."
}
```

This contract is intentionally separated from the current V2 HTML field names. The V3 frontend adapter will map form field names to this API contract before switching production from Google Apps Script to Yandex API Gateway.
