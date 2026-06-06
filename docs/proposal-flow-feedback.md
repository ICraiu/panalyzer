# Proposal Flow Feedback

This note captures feedback from using the current proposal flow to create and submit a test proposal that merges `project_registry` into `project_service`.

## What Went Well

- The core docs were sufficient to complete the flow. `proposal-flow.md`, `merge-spec.md`, and `transition-authoring-guide.md` together described the model well enough to build a valid proposal.
- The proposal validator is strict in a useful way. Once the exact method and reference identities were known, it was possible to validate the proposal with confidence before submission.
- The `project_sha` pinning model is clear and easy to understand.
- Proposal persistence worked cleanly. After submission, the proposal was stored under the project-specific proposals directory as described.
- The merged graph output was informative. It clearly marked `project_registry.py` as `remove`, `project_service.py` as `change`, and surfaced added and removed method-level edges.
- Warnings were useful. They highlighted ambiguous `change` semantics without blocking the proposal.

## What Went Bad

- The process is too manual for non-trivial proposals. A realistic refactor required extracting exact class, method, and reference identities before authoring JSON.
- The required explicitness is expensive. Removing one file and moving its behavior into another required declaring many methods and references individually.
- The default architecture view is not enough for authoring anything beyond a very small proposal. In practice, the method/reference layer is required early.
- There is no first-class proposal authoring loop in the app. The flow still depends on CLI inspection, hand-built JSON, and direct POST submission.
- The latest-proposal-only behavior is fragile during experimentation. A bad last submission can block normal graph viewing for the project.
- The current `change` semantics are narrow enough that refactor proposals feel awkward. For example, a constructor wiring change or service relocation may not fit naturally into "signature adaptation" language.
- There is no easy built-in way to preview which exact nodes and edges will change before saving the proposal.

## Friction Points Seen In Practice

- Discovering exact project ids was awkward without a dedicated CLI helper or explicit UI copy action.
- Extracting architecture for a real repo can be slow enough that iterative proposal authoring becomes cumbersome.
- The graph endpoint is the only practical way to inspect the merged result, but the user has to infer proposal-specific changes from rendered states.
- Added methods that do not yet exist in scan truth show up with synthetic line values such as `L0`, which makes the result look less grounded.

## Suggested Improvements

- Add a proposal export helper that emits the current scan as proposal-ready identities for selected files.
- Add a dry-run endpoint that validates and renders a proposal without making it the active latest proposal.
- Add a proposal list and selection UI so testing multiple proposals does not depend on last-write-wins behavior.
- Add a focused diff summary to the graph response:
  package changes, file changes, method changes, and reference changes grouped separately.
- Add a helper for common refactor patterns such as move/merge file, so the user does not need to enumerate every removed and re-added reference by hand.
- Make proposal warnings easier to interpret by linking them to concrete graph nodes or edges in the UI.

## Overall

The flow is already usable for careful testing, and the merge engine appears coherent. The main weakness is authoring cost: the system expects proposal precision at a level that is hard to produce efficiently without better tooling around scan extraction, draft generation, preview, and iteration.
