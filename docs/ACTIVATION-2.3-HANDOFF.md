# Legal 2.3 activation / final RC

Owner decision: Влад, 14.10.2026, approved draft source a0a6c6f6199b9d29096a9fa6d935724b4d24860b. Approval date is fixed; application begins only at actual publication on club-gravitation.ru. No publication, merge, production deployment or migration has occurred. RKN PDF/registry are excluded from current release gates by the owner; the earlier comparison remains historical context.

## Legal and contract

Approved sources: legal/frozen/FORM-2.3.txt, CONSENT-PD-2.3.txt, PPD-2.3.txt. Only the approval date/effective-publication condition were completed from the approved drafts. Archived 2.2 files remain unchanged. Approval record: legal/approval-2.3.json.

| Source | Canonical SHA-256 |
|---|---|
| CONSENT-PD-2.3 | 10f8c02d5c034d06c09f80a5f4b67bebbcdc98fcd8d18b4b95718338ac50f8c2 |
| PPD-2.3 | caa57445997081c4df49ff71b346cd1a6ba4282b7408cfbcde0b97d5590d4445 |
| FORM-2.3 | 720468a4df6a967f88cd023e5fa0136f93549ef5824114d4710875a5c570d3bb |

Canonicalization is unchanged: UTF-8, leading BOM removed, CRLF/CR→LF, NFC, trailing spaces/tabs removed per line, empty trailing lines removed, one final LF. Evidence hashes source text rather than HTML. Frontend and Python use exact FORM/CONSENT/PPD 2.3; public routes fetch frozen 2.3; all 2.2 sources remain in archives. TEST marks the version-specific digest with TEST-, PROD uses the bare digest.

Existing 2.2 records/evidence and idempotent replays remain unchanged. Short-form fingerprints include the legal contract, preventing a previous synthetic FORM-2.3/Consent-2.2 replay from claiming Consent-2.3. Duplicate submissions retain the original application/evidence and number. No schema changes. After activation, new PROD 2.2 submissions require reload; V5_ALLOW_LEGACY_INTAKE must remain false. The parser and existing history are preserved.

## Verified RC

188 Python tests and 9 JS suites: activation, canonical/frozen integrity, exact versions/evidence, legacy history/replay, YDB version-specific hashes/environment, production package and isolated runtime; public/artifact/Admin/deployment safety. Public build defaults to PUBLIC_BLOCKED. An explicit PROD_ENABLED build accepts only the exact PROD API endpoint and approved frozen texts/hash. CI is checked on the final Git SHA. Earlier accepted responsive/cloud TEST E2E and operator photo gate remain valid; no new cloud deployment performed for activation.

Targeted synthetic TEST data-plane integration PASS: existing private TEST photo initiate/PUT/complete, local new activation handler and real TEST YDB transaction. Application №000019 (`APP-24228b9faabc13b2ba31`) stores exact 2.3 versions and `TEST-10f8c02d…50f8c2`; replay returns the same number. Historical №000018 consent evidence compared before/after and unchanged. This is not a claim that the new handler was deployed to cloud; the accepted TEST function version remains unchanged. The synthetic record/photo were retained; no cleanup or counter reset. Local proof: test-results/activation-2.3-integration.json.

Production package is rebuilt from current source plus restored PROD runtime from snapshot b306cf4, using build_production.py; not copied from a TEST ZIP. Its manifest records source SHA, clean-source state, per-file hashes, PROD target, approval and legacy contract. Original September ZIP byte equivalence remains unproved; retained cloud version is the primary backend rollback point.

Live PROD verified read-only: Function d4e8kk0f5bqulombl18j, active d4ej2creip5g0iloi3vh ($latest), python314, 512 MiB, 30 s; current consent hash remains 2.2 (`7a4ed027…6bf7`). TEST/PROD databases and buckets are distinct. No anonymous function invocation binding was found. TEST remains d4ev92fcfmgoj0sfr64f; operator/photo UI gate previously passed.

## Artifacts

Generated locally in backend/v5/dist: production-rc.zip; frontend-production-rc.tar.gz; frontend-public-blocked-rc.tar.gz; release-manifest-2.3.json with final source SHA and SHA-256 for every artifact. Neither ZIP nor tar is uploaded/deployed. The release manifest excludes secrets and signed URLs.

Gateway specs are also local, not applied: prod-api.baseline.yaml (exact current readback), prod-api.pinned-2.2.yaml (all seven function integrations pinned to stable-2-2), prod-api.release-2.3.yaml (release-2-3), prod-api.maintenance.yaml (three public POST routes return 503; protected Admin routes/auth remain unchanged). gateway-plan-proof.json records checksums and preservation checks. Baseline hash at readback: 761b08b996399630dbea12edf26c5c69b95a2bb50293fbba9c8702f37d90f9b7. Re-read before execution; stop if actual version/spec changed.

## Safe release — only after separate owner authorization

1. Verify final Git SHA/green CI/manifest hashes, current frontend release ID and active backend d4ej2creip5g0iloi3vh. Save current Gateway spec and version configuration/secrets references without printing credentials. No migration required.
2. Retain the current backend under a stable tag: `yc serverless function version set-tag --id d4ej2creip5g0iloi3vh --tag stable-2-2`. Apply pinned-2.2 Gateway spec, then maintenance spec to close /applications and both /photo-uploads POST routes. Preserve JWT/CORS/IAM. Verify maintenance 503 and protected Admin. A new function version automatically gets $latest; the Gateway pin prevents accidental promotion during upload ([Yandex tags](https://yandex.cloud/ru/docs/functions/operations/function/tag-add), [Gateway tag default](https://yandex.cloud/ru/docs/api-gateway/concepts/extensions/cloud-functions)).
3. Create a new version of the existing PROD function from production-rc.zip with tag release-2-3, same service account, python314/512 MiB/30 s and existing PROD database/bucket settings. Set V5_ENVIRONMENT=PROD, V5_PROD_CONSENT_TEXT_HASH to the full canonical 2.3 hash above and V5_ALLOW_LEGACY_INTAKE=false. Do not use TEST env/hash/bucket. Verify isolated tag health and packaged legal integrity; public writes remain closed.
4. Dispatch selectel-deploy.yml on the exact final RC ref with operation=deploy and public_mode=PUBLIC_BLOCKED (the safe default), or deploy the verified blocked tar through scripts/selectel-release.sh. Confirm exact frozen 2.3 pages, archives and hashes over production HTTPS. This is the actual start of application; record its timestamp/release ID. Keep intake closed until these checks pass.
5. Apply release-2.3 Gateway spec (new backend), then dispatch the same exact RC ref with public_mode=PROD_ENABLED, or atomically activate frontend-production-rc.tar.gz. A workflow rebuild must record its own archive checksum; all canonical legal hashes and source SHA must match the accepted RC. Verify form/config/versions, private photo/CORS, permitted synthetic control submission and consent evidence plus protected operator card under the agreed release acceptance. No real personal data are needed for control QA.
6. Keep the PR draft until final acceptance; merge is a separate authorized action. Do not run deploy/merge from this preparation task.

## Independent rollback

Close public writes with the maintenance Gateway spec before rollback. Activate the PUBLIC_BLOCKED 2.3 frontend artifact, retaining the published legal texts and archives. Maintenance serves protected reads through stable-2-2, restoring the preserved backend version independently of the frontend symlink. Verify health/Admin and closed writes. Do not reset counters, delete applications, rewrite evidence or restore the database. Reopening an old 2.2 frontend/intake is a separate owner decision; an automatic old frontend rollback must not silently hide the published 2.3 legal archive.

The existing Selectel symlink rollback alone is insufficient for backend/legal rollback. The retained function version and saved Gateway spec/tag are the independent mechanism; no rebuild of the missing September ZIP is required.

## Acceptance decision

RC is prepared for production acceptance. Legal approval is recorded; RKN PDF/registry are outside current gates. Remaining action from the owner: separately authorize the exact release/controlled acceptance procedure. PROD remains unchanged until then.
