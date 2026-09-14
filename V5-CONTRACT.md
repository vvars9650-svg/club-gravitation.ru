# V5 application contract

`POST /applications` is TEST-only and accepts `application/json` and `Idempotency-Key`.

The canonical payload uses internal `form_version: "FORM-2.2"` and legal versions
`PPD-2.2` / `CONSENT-PD-2.2`. Both `policy_acknowledged: true` and
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

Photo status is `PHOTO_REQUIRED_LEGAL_APPROVED`. `photo_object_id` is required in
FORM 2.2. It is an opaque protected-object reference, never a public URL, original
filename, binary value, or base64 value. A file input alone cannot satisfy submit:
the backend must resolve a validated reference owned by the same random upload
context used for the pending submission. Exactly two legal checkboxes remain; photo
does not introduce another consent checkbox.

An Application snapshot permanently retains the photo reference used at submit.
Participant has a separate `current_photo_object_id`. An explicit replacement may
switch the Participant reference and schedule the old object for deletion, but it
never rewrites an Application. A candidate replacement before a decision follows
the same rule: Admin uses the current Participant photo while the submitted
Application remains historical evidence. An approved Participant replacement also
switches only the current reference.

`PHOTO_DELETION` stops active photo use immediately and requests object deletion;
it never deletes the Participant or Application. An approved Participant stays
approved and active. A candidate with no current photo is marked unable to continue
selection until an operator makes an explicit later decision.

The Phase B upload design is: browser asks the controlled backend for an upload
context; backend returns an opaque object reference and a narrowly scoped upload;
the browser uploads to a private Yandex Object Storage bucket; backend verifies and
normalizes the image, then marks the reference ready; `POST /applications` reserves
that owned reference and attaches it to the immutable Application. Admin reads the
photo through an authenticated backend proxy (recommended over exposing signed URLs
to ordinary exports or logs). There is no permanent public URL or foreign CDN.

Accepted technical configuration is JPEG, PNG, or WebP up to 10 MiB. Detection is
from decoded content, not extension. Decode must succeed. Persistent content is a
fresh re-encode with GPS, device model, original timestamps, and other unnecessary
EXIF/metadata discarded. The phrase "на которой хорошо видно вас" is guidance
only: no face detection, scoring, recognition, matching, biometric authentication,
identity confirmation, or automated decision-making is permitted.

Rejected or stopped-selection photos are destroyed with working data no later than
30 days after purpose ends. Approved photos may remain while the purpose exists.
Inactive Participants retain the 12-month meaningful-interaction review and 30-day
destruction rule. Confirmed photo-only deletion stops use immediately, deletes the
active object without unjustified delay, and requires backup expiry within 14 days.

Logs and mass exports exclude image bytes, base64, filenames, EXIF, permanent URLs,
and presigned URLs. Minimal logs may contain only `photo_object_id`, operation,
status, request ID, and an error code.

Migration 006 is additive preparation and is not applied. FakeRepository proves the
domain lifecycle only; YDB photo reservation and object operations fail closed until
Phase B implements and integration-tests them. No cloud security guarantee is
claimed by an in-memory test double.

Technical implementation may proceed in synthetic TEST. Real PROD photo collection
remains `PROD_PHOTO_RKN_GATE_PENDING`: RKN-02 is processing and RKN-03 is not yet
filed and confirmed. PROD is NO-GO until that gate is explicitly cleared.
