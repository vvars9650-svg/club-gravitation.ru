# V5 application contract

`POST /applications` (deployment route is deliberately not configured) accepts `application/json` and `Idempotency-Key`.

The payload must include `submission_mode: "TEST"`, `form_version: "FORM-2.0"`, `personal_data_consent: "true"`, and legal versions `PPD-2.0` / `CONSENT-PD-2.0`. `public_profile_url` is optional and, when present, must be HTTP(S).

The supplied handler is a TEST-only reference implementation. It has no Yandex Cloud, YDB, Google Apps Script, photo-upload, or Base64 integration. A future production design must be separately approved and must not be enabled merely by setting a browser endpoint.
