# Migration 008: explicit TEST data-plane runner

Nothing in this document was executed against YDB during implementation.
The runner is an operator tool, not part of the Cloud Function package/startup.
Use only the reviewed synthetic TEST database. PROD is out of scope.

## Connection and authorization

Install the exact dependencies from `backend/v5/requirements.txt` in the local
operator environment. Use that environment's Python executable. Supply a
pre-provisioned short-lived token securely through `YDB_ACCESS_TOKEN`; never put
the token on the command line or into the repository. The runner uses
`ydb.AccessTokenCredentials`, not IAM token creation, metadata lookup or Cloud
control-plane APIs. No contacts, token, endpoint/database, query parameters or
SDK exception text are printed. Run without SDK debug logging.

Endpoint/database are mandatory explicit inputs. `--environment TEST` is
mandatory; omitted/PROD values fail before connecting. This guard does not prove
that an operator-supplied database is TEST: review the target identifiers before
issuing any write. Phases default to read-only, including `backfill` and `register`.

PowerShell setup (replace the two placeholders with reviewed TEST values):

```powershell
$crmArgs = @('--environment', 'TEST', '--endpoint', 'grpcs://<TEST-ENDPOINT>:2135', '--database', '/<TEST-DATABASE>')
```

## 1. Read-only preflight and inventory

```powershell
python -m backend.v5.migration_008_runner @crmArgs --phase preflight
python -m backend.v5.migration_008_runner @crmArgs --phase inventory
```

Preflight uses YDB Scheme list-directory and Table DescribeTable data-plane
calls. It checks all eleven 008 application columns and both key tables,
including column types and ordered primary keys. Result states are
`not_started`, `partial`, `schema_ready`. Missing/incompatible schema produces
`FAIL`/exit 1; fully ready produces `PASS`/exit 0. An initial missing schema is
an expected reason to review the schema phase, not permission to skip it.
Inventory can read the 001–007 baseline before 008 columns/tables exist.

Inventory outputs only counts, technical Application/Participant IDs, numbers,
submission timestamps and group IDs derived from Application IDs (not hashes
of guessable phone numbers). Normalized phones remain internal query parameters.
Canonical selection: earliest UTC submission, then smallest positive number
(missing/zero last), then Application ID. No numbers are allocated or changed.

STOP if the target/environment is wrong, baseline 001–007 is incomplete, schema
types/keys are incompatible, or the ID-only inventory is unexpected. Stop if
an existing 008 ledger entry accompanies failed verification. Do not repair or
delete that ledger entry automatically.

## 2. Apply only missing schema objects

Pause ALL TEST writers: intake function, photo/lifecycle jobs, Admin writes and
other operators. Keep them paused through verification/registration. Also
serialize schema operations; the runner does not create a distributed DDL lock.
`--writers-paused` is an operator assertion, not an automatic maintenance switch.

```powershell
python -m backend.v5.migration_008_runner @crmArgs --phase schema --allow-write --writers-paused
python -m backend.v5.migration_008_runner @crmArgs --phase preflight
```

Only missing statements from `schema/008_admin_crm_v2.sql` execute. Schema is
inspected before every statement and again at completion. No column/table is
dropped, altered to another type, or blindly recreated. After a partial DDL
failure or lost response, rerun this same phase: objects already present are
skipped. Do not replay the raw SQL file. Incompatible types/keys require manual
review. The schema phase does not register 008 or run backfill.

STOP unless preflight reports `schema_ready` and `PASS`.

## 3. Backfill

Review a fresh inventory after schema completion, then explicitly execute:

```powershell
python -m backend.v5.migration_008_runner @crmArgs --phase inventory
python -m backend.v5.migration_008_runner @crmArgs --phase backfill --allow-write --writers-paused
```

One serializable transaction per phone group rereads current TEST state and
atomically upserts the canonical phone key, missing status/next-action defaults,
stable audit events, the convergent duplicate summary, and (when needed) the
canonical Application number plus its counter advancement. Missing canonical
numbers are allocated in deterministic canonical Application-ID order, above
both the current counter and every already-positive Application number. Existing
positive numbers are authoritative; retained later duplicate Applications stay
unnumbered unless they already had a positive number. The number update and
counter UPSERT commit in the same transaction, so a retry cannot allocate a
second number to an already-numbered canonical Application. Audit ID is SHA-256
of migration ID + canonical Application ID + later Application ID. The action
contains the normalized-phone basis, migration source and later technical ID.
Duplicate summaries are computed as `later rows + existing runtime hard-duplicate
events`, never blindly incremented. Existing meaningful status/action, owner, priority,
comments and other operational fields remain untouched. Application form/content,
consents, photos and participants are never deleted, merged or rewritten by this
runner; only the canonical operational defaults, duplicate summary and missing
number are updated. Later application snapshots remain intact.

A transaction failure rolls back that group's key/events/summary together.
Previously committed groups remain valid; rerun the phase to converge to the
same final state. Existing conflicting key targets or unexplained legacy
duplicate events require manual review, not automatic reassignment/cleanup.

STOP on `FAIL`, missing participant, duplicate canonical numbers, an invalid or
regressed counter, unexpected audit evidence or conflicting key. A failed run
must be resumed and verified before registration. A nonpositive canonical
number is an expected pre-backfill state; the backfill assigns it transactionally
and verification must pass afterward. Do not allocate replacement numbers for
Applications that already have positive numbers.

## 4. Independent read-only verification

```powershell
python -m backend.v5.migration_008_runner @crmArgs --phase verify
```

Verification requires complete schema, prior migration ledger entries, exact
canonical key coverage, valid Application/Participant references, one visible
canonical per group under the Admin inner-join contract, positive unique visible
numbers, sequence counter at least the maximum number of ALL existing rows,
correct defaults, exact stable reconciliation audit identities and matching
duplicate summaries. A pre-existing 008 ledger entry with inconsistent state
is explicitly reported as `migration_incorrectly_registered`.

STOP unless JSON `result` is `PASS` and the process exits 0. Schema-ready or a
successful backfill command alone is insufficient. Retain the ID-only output.

## 5. Register the final ledger entry

```powershell
python -m backend.v5.migration_008_runner @crmArgs --phase register --allow-write --writers-paused
python -m backend.v5.migration_008_runner @crmArgs --phase verify
```

Registration independently repeats full verification and checks/inserts the
ledger in ONE serializable transaction; it does not trust a file, supplied
counts or flags from a previous process. Existing valid registration is a no-op
(the original timestamp is preserved). There is no intermediate `008 complete`
ledger state. `ledger_complete=true` plus verification PASS is required before
considering deployment; this tool never deploys a function.

STOP if final verification fails or ledger_complete is false. Do not resume
writers/deploy on an incomplete rollout. Keep TEST paused while resolving the
failure with a separately reviewed action.

## Scope and validation limits

This is intentionally a small synthetic TEST runner: it scans TEST rows in
memory and rereads them per group for simple transactional recovery. Large
datasets may exceed YDB transaction/time limits; STOP rather than weakening
verification. Backfill/register never chain other write phases. No live YDB
execution is part of the local unit suite; tests exercise the real adapter's
query path with an atomic data-plane double, not a YDB server/query compiler.

The runner's data verification is NOT a guarantee that the existing Cloud
Function's YQL is valid. The committed baseline's intake query currently has a
semicolon before the secondary-match `UNION ALL` in `YdbRepository.save`; its
phone-duplicate choice also sorts by number/ID rather than the migration's
timestamp-first rule and does not consult the canonical key there. These
pre-existing runtime issues require separate correction/verification before
Cloud Function rollout or resuming intake against reconciled historical groups.
The runner does not modify that runtime in this task.
