---
name: gravitation-visual-qa
description: Run Gravitation public-frontend visual and responsive QA. Use for visual review, viewport checks, annotation-driven fixes, screenshots, overflow/clipping checks, and final frontend visual acceptance.
---

# Gravitation visual QA workflow

1. Ground the task:
   - confirm repo/worktree/branch/status before edits;
   - read the specific page task and applicable AGENTS.md rules;
   - do not reopen already accepted visual areas without a concrete regression.

2. Build and preview using the current canonical project workflow.
   - verify the preview artifact was built from the current worktree;
   - for the established static public frontend, use the repo's documented build/preview commands;
   - do not substitute a stale running server for a fresh build.

3. Use browser/visual tooling only for UI work.
   - do not invoke visual/browser tooling for backend-only tasks;
   - preserve the current browser session when continued annotation/login state is useful.

4. Default responsive matrix when the task does not specify another:
   - desktop 1440x900 DPR1;
   - desktop HiDPI 1440x900 DPR2;
   - mobile 390x844 DPR3;
   - narrow mobile 360x800 DPR3;
   - tablet only as regression smoke unless explicitly in design scope.

5. Check:
   - horizontal overflow;
   - clipping/collisions/overlays;
   - typography and spacing regressions relevant to the task;
   - CTA/navigation behavior;
   - image sharpness/cropping when changed;
   - console errors/warnings and failed network requests;
   - environment gates relevant to the page.

6. Annotation workflow:
   - gather a coherent batch of desktop annotations before patching;
   - apply one focused batch and rebuild once;
   - gather mobile annotations separately and patch as one batch;
   - do not run a full final audit between every tiny annotation unless requested or risk requires it.

7. Keep fixes minimal:
   - preserve approved content, visual direction and responsive behavior outside scope;
   - avoid unrelated redesign or global CSS cleanup;
   - if a shared rule changes, smoke-check the other pages it can affect.

8. Final acceptance:
   - run the task-required automated checks and git diff --check;
   - repeat the relevant viewport matrix;
   - capture screenshots when they materially prove the result;
   - return a short HANDOFF with files changed, checks, remaining limitations and whether the page is accepted for the next release stage.
