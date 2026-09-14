# Legal text dependency

The approved frozen sources are present and must not be edited in place:

- `legal/frozen/PPD-2.2.txt`
- `legal/frozen/CONSENT-PD-2.2.txt`
- `legal/frozen/FORM-2.2.txt`

`CONSENT-PD-2.2.txt` is decoded as UTF-8, stripped of a BOM, normalized from CRLF/CR
to LF and Unicode NFC, stripped of trailing spaces/tabs per line, stripped of
trailing empty lines, terminated with exactly one LF, encoded as UTF-8, and hashed
with SHA-256. The verified value is
`7a4ed02773773d680bb56399c943b94e2f35cf97d96b89a29e156d132fca6bf7`.
`FROZEN_CONSENT_2_2_VERIFIED` is true and protected by a permanent regression test.

Public Policy and Consent pages load these exact frozen text sources as text, not as
HTML-derived legal evidence. Public copy does not display technical version IDs.
The form keeps exactly two independently required, initially unchecked legal
checkboxes and the Consent date 14.09.2026.

Required photo is legally approved (`PHOTO_REQUIRED_LEGAL_APPROVED`) for the stated
ordinary-personal-data use case. Real PROD collection remains disabled under
`PROD_PHOTO_RKN_GATE_PENDING` until the separate RKN gate is cleared.
