---
name: gravitation-release
description: Run a controlled Gravitation site release or deployment. Use for build, release-readiness checks, Selectel/Yandex deployment, live smoke, rollback verification, and final release handoff.
---

# Gravitation release workflow

1. Start from facts, not handoff assumptions:
   - confirm repo, worktree, branch, HEAD, git status and diff;
   - read only the current release task and the minimum relevant project sources;
   - do not use a path copied from another computer without verifying it exists here.

2. Protect unrelated work:
   - do not reset, stash, discard or overwrite unknown local changes;
   - if the working copy is dirty outside scope, use an isolated worktree from the approved baseline;
   - package/deploy only from the verified target worktree.

3. Respect release authority:
   - commit, push, deploy, DNS, cloud and production mutations require explicit authorization in the current task;
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
