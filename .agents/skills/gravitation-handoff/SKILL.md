---
name: gravitation-handoff
description: Prepare a compact Gravitation context transfer when finishing a major stage or moving to a fresh Codex chat. Use for HANDOFFs, session rollover, or recovering work without carrying long chat history.
---

# Gravitation handoff workflow

Use this skill when a major stage is complete, the next task is substantially independent, or the current conversation has become noisy enough that old context costs more than it helps.

1. Re-check the actual state before writing the handoff:
   - repo/worktree/branch/HEAD/status;
   - commit/push/PR/deploy state when relevant, including actual GitHub remote SHA readback; distinguish local-only files, untracked files and released TEST artifact;
   - latest task-relevant Drive/Sheet source if available;
   - actual environment state for anything claimed as deployed.

2. Keep only continuation-critical facts.

Required shape:

## Result
What is actually complete and the acceptance result.

## Where
Permanent result first: GitHub repo, pushed branch, verified remote commit SHA/PR; Drive links for decision/media; actual deployed TEST/PROD IDs and URLs. Worktree/localhost only as temporary context if still needed. If code is untracked/local-only or exists solely on TEST, flag `PERSISTENCE BLOCKED`, never `DONE`.

## Verified
Only checks that were actually run and their outcomes.

## Current blocker
One exact blocker, or "none".

## Next task
The next executable objective and its completion criteria.

## Guardrails
Only constraints that the next session could otherwise violate, such as protected dirty worktree, TEST/PROD separation, no-forged-auth, or no-destructive-action rules.

3. Exclude:
   - chronological history of attempts;
   - full command logs;
   - resolved hypotheses;
   - repeated architecture explanations already stored in canonical sources;
   - secrets, tokens, private keys or real personal data.

4. Prefer references over duplication:
   - point to canonical Drive docs, Sheet rows, repo files or commits;
   - if the next executor cannot access a source, include only the minimum necessary excerpt with source/date.

5. Fresh-chat rule:
   - recommend a new Codex chat when the previous major stage is closed and the next one does not benefit materially from the accumulated conversation;
   - keep the same chat for a continuing blocker where recent diagnostic context is still useful;
   - do not use an arbitrary token-count threshold as the decision rule.

6. The receiving session must verify repo/branch/HEAD/status and relevant live sources before making changes. A handoff is a compact transfer, not an authority that overrides current facts.

7. Mandatory close-out for coding tasks: apply the project's current permissions; commit+push the task-only verified source to a separate GitHub branch, confirm remote readback, note reproducible build artifact/manifest where relevant, and only then mark DONE. If push is impossible or explicitly prohibited, report exact `PERSISTENCE BLOCKED` and retain safe material. Local worktree, transient cloud environment, TEST deploy and QR are not source repositories. Do not ask Vlad to install GitHub Desktop or operate shell/SSH manually.
