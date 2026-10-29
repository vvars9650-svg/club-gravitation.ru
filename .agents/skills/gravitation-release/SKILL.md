---
name: gravitation-release
description: Run a controlled Gravitation site release or deployment. Use for build, release-readiness checks, Selectel/Yandex deployment, live smoke, rollback verification, and final release handoff.
---

# Gravitation release workflow

Default development/deployment environment: the home PC. Before Selectel CLI work, read the canonical [SSH/CLI runbook](../../../docs/SELECTEL-SSH-CLI.md) for the verified alias, identity and TEST permission limits.

Public TEST has a separate [deploy/rollback runbook](../../../docs/SELECTEL-TEST-DEPLOY.md). The fixed TEST entrypoint was installed and live-tested on 2026-10-18. Use status/deploy/rollback from a fresh SSH process; do not use the PROD release script, reinstall access, repeat key diagnostics or change sudoers. Reconcile actual status with the recorded installation handoff before an authorized deploy. Public TEST authorization never includes TEST Admin or PROD. Preserve PUBLIC_BLOCKED and all protected files.

On 2026-10-19 Vlad authorized a bounded installed-policy extension for `terms/index.html` and `offer/index.html`. These two existing HTML paths now use the same normal SSH TEST deploy; do not ask to reopen a root console for subsequent content releases on those paths. All frozen legal TXT, apply, JS/config, PPD/CONSENT-PD and Admin remain protected. See [legal TEST policy update](../../../docs/LEGAL-SBP-TEST-20261019.md). An out-of-allowlist rejection is a policy-scope issue, not an SSH failure; never recreate keys or expand sudoers to solve it.

1. Start from facts, not handoff assumptions:
   - confirm repo, worktree, branch, HEAD, git status and diff;
   - read only the current release task and the minimum relevant project sources;
   - do not use a path copied from another computer without verifying it exists here.

2. Protect unrelated work:
   - do not reset, stash, discard or overwrite unknown local changes;
   - if the working copy is dirty outside scope, use an isolated worktree from the approved baseline;
   - package/deploy only from the verified target worktree;
   - for completed code tasks, preserve reproducible source and build scripts in remote GitHub before considering the job DONE. If TEST was deployed from untracked-only local files, treat source persistence as a priority recovery task and do not erase the worktree; TEST live does not prove code is safely stored.

3. Respect release authority:
   - safe task-scoped commit+push to an isolated GitHub branch is covered by Vlad's standing authorization of 2026-10-29, unless the current task explicitly forbids it; verify diff, source provenance, absence of secrets/private data and remote SHA readback;
   - merge/main/v5, deployment, DNS/cloud mutations, server permissions, destructive changes and PROD still require separate authorization; public TEST may be deployed only via the already-approved scoped TEST manager and within its allowlist;
   - do not re-open already accepted gates unless new evidence contradicts them;
   - never weaken auth, privacy, validation, environment isolation or fail-closed behavior to make a check pass.

4. Before deployment:
   - run the task-relevant canonical build and tests;
   - run git diff --check and repo safety/contract checks that apply;
   - verify environment-specific config points to the intended TEST or PROD resources;
   - confirm no secret, private backend file or test-only configuration leaks into the public artifact.

5. Deploy through the existing proven project mechanism.
   - Codex performs routine terminal/SSH/deploy commands itself when credentials are already available;
   - ask Vlad only for interactive password, passphrase, 2FA, UAC, secret or external approval that cannot be completed autonomously;
   - never ask Vlad to copy private keys or tokens into chat.

6. After deployment:
   - verify the actual deployed environment, not merely the commit;
   - perform the smallest sufficient live smoke for affected routes;
   - for public frontend releases, verify the task-required public routes, console/network errors and environment gates;
   - for intake/admin changes, verify the real protected/data path required by the task.

7. Rollback:
   - identify the last known-good artifact/commit and the practical rollback path before declaring the release complete;
   - if live verification fails materially, stop expansion and either roll back when authorized or return the exact blocker.

8. Return a short HANDOFF:
   - what is live;
   - branch/HEAD/commit/push state;
   - environment and URLs checked;
   - checks and outcomes;
   - rollback state;
   - only unresolved issues and the exact next action.

Do not include long logs or a history of failed attempts unless needed to continue the work.
