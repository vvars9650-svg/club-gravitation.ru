# V5 application contract

`POST /applications` is TEST-only and accepts `application/json` and `Idempotency-Key`.

The payload must include `form_version: "FORM-2.1"`, `personal_data_consent: true`, and legal versions `PPD-2.0` / `CONSENT-PD-2.0`. `telegram` is the optional profile-or-messenger field; `public_profile_url` is the optional page-or-site field and, when present, must be HTTP(S). `comfortable_price` is not accepted or retained for FORM-2.1.

The supplied handler is a TEST-only reference implementation. It has no Yandex Cloud, YDB, Google Apps Script, photo-upload, or Base64 integration. A future production design must be separately approved and must not be enabled merely by setting a browser endpoint.

