# Merge Spec

## Purpose

This spec defines how Panalyzer accepts an explicit change proposal on top of a scanned target repository.

The goal is to let an LLM propose work in strict architectural terms:

- packages
- files
- methods
- method-level references

The proposal must be explicit. The system validates consistency and reports all detected errors. The UI renders exactly the validated merged result and does not infer missing changes.

## Existing Models

The current models keep these responsibilities:

- `Project`: scan truth for the target repository
- `Diagram`: simplified package/file/transition view
- `Graph`: interactive UI view

`Project` remains pure scan truth. It does not carry proposal state.

## Core Rule

Method-level references are the only authored relationships in the system.

This is a hard rule:

- references are always method-level
- file-level transitions are derived from method references
- package-level relationships are derived from method references

The proposal never declares file-level or package-level transitions directly.

## Identity Rules

Proposal objects use these identities:

- package: `name`
- file: `relative_path`
- method: `qualname`
- reference: `(source_method, target_method, file_relative_path)`

`relative_path` is always relative to the analyzed project root.

Reference identity is intentionally aggregated:

- one proposal reference represents the relationship between one source method and one target method within one file
- if the same source calls the same target many times in the same file, it is still modeled as one proposal reference

The system does not model per-callsite reference identity in this version.

## State Model

There are two state contexts.

Proposal state:

- `add`
- `change`
- `remove`

Merged/rendered state:

- `present`
- `add`
- `change`
- `remove`

`present` is not allowed in proposal input.

Reference `change` has a narrow meaning:

- the same source method still calls the same target method
- the relationship remains
- the callsite changed because the target method signature or callable contract changed

Reference `change` does not mean generic call-behavior change in this version of the spec.

## Proposal Model

The proposal is a separate model from `Project`.

Proposal artifacts are persisted and belong to a specific project.

Each saved proposal must include metadata:

- `id`
- `name`
- `created_at`
- `author`
- `source_model`
- `rationale`
- `project_sha`

`project_sha` is required and must be non-null.

Proposal persistence is file-based:

- proposals are stored under a configured proposals root
- each project has its own folder
- each proposal is stored as a JSON file inside that project folder

Each proposal is pinned to the SHA it was authored against.

Example shape:

```json
{
  "id": "proposal_20260604_001",
  "name": "Extract merge validation service",
  "created_at": "2026-06-04T10:15:00Z",
  "author": "codex",
  "source_model": "gpt-5",
  "rationale": "Split validation out of the CLI flow.",
  "project_sha": "abc123def456",
  "packages": [],
  "files": [],
  "methods": [],
  "references": []
}
```

Example object shapes:

```json
{
  "packages": [
    {
      "name": "project_analyzer.merge",
      "relative_path": "src/project_analyzer/merge",
      "iteration_state": "add"
    }
  ],
  "files": [
    {
      "relative_path": "src/project_analyzer/merge/service.py",
      "import_path": "project_analyzer.merge.service",
      "package_name": "project_analyzer.merge",
      "iteration_state": "add"
    }
  ],
  "methods": [
    {
      "qualname": "project_analyzer.merge.service.apply_merge",
      "name": "apply_merge",
      "file_relative_path": "src/project_analyzer/merge/service.py",
      "signature": "def apply_merge(...)",
      "iteration_state": "add"
    }
  ],
  "references": [
    {
      "source_method": "project_analyzer.cli.main",
      "target_method": "project_analyzer.merge.service.apply_merge",
      "file_relative_path": "src/project_analyzer/cli.py",
      "iteration_state": "change"
    }
  ]
}
```

## Explicitness Rule

The proposal must be explicit.

The system does not derive missing package, file, method, or reference changes from adjacent declarations.

Examples:

- if a new method is proposed, its containing file must also be proposed
- if a new file is proposed, its containing package must also be proposed
- if a removed method has incoming or outgoing removed references, those references must also be proposed explicitly

The validator reports missing required declarations as errors.

## Required Explicit Declarations

The proposal must explicitly declare every touched element that participates in the authored change set.

Required declarations:

- if a method is declared, its containing file must also be declared
- if a file is declared, its containing package must also be declared
- if any contained method is non-`present` in the merged result, the file declaration is required in the proposal
- if any outgoing reference from a method in a file changes, the file declaration is required in the proposal
- if any contained file is non-`present` in the merged result, the package declaration is required in the proposal
- if any outgoing reference change touches a file in a package, the package declaration is required in the proposal

Direction matters:

- changed outgoing reference from method `A` requires an explicit declaration for method `A`
- changed outgoing reference from method `A` requires an explicit declaration for the containing file of `A`
- changed outgoing reference from method `A` requires an explicit declaration for the containing package of `A`
- changed incoming reference to method `B` does not require an explicit declaration for method `B` unless `B` itself changes

The system validates these declarations. It does not invent them.

## Existence Rules

For all objects, existence is checked against the scanned `Project`.

Rules:

- existing package: allowed states are `change`, `remove`
- non-existing package: allowed state is `add`

- existing file: allowed states are `change`, `remove`
- non-existing file: allowed state is `add`

- existing method: allowed states are `change`, `remove`
- non-existing method: allowed state is `add`

- existing reference: allowed states are `change`, `remove`
- non-existing reference: allowed state is `add`

Invalid examples:

- existing file with `add`
- non-existing method with `remove`
- any proposal object with `present`

## Parent-State Validation

Parent state is declared explicitly and validated against children.

Parent state is not derived automatically.

### File Rules

File `add` is valid only when:

- the file does not already exist
- all declared methods in the file are `add`

File `remove` is valid only when:

- the file already exists
- all existing methods in the file are explicitly declared `remove`
- all existing references touching methods in the file that are removed as part of the proposal are explicitly declared `remove`

File `change` is valid when:

- the file already exists
- the file is neither a pure add nor a pure remove
- at least one contained method or relevant outgoing reference change touches the file

### Package Rules

Package `add` is valid only when:

- the package does not already exist
- all declared files in the package are `add`

Package `remove` is valid only when:

- the package already exists
- all existing files in the package are explicitly declared `remove`
- all existing methods in those files are explicitly declared `remove`
- all existing references touching removed methods in the package are explicitly declared `remove`

Package `change` is valid when:

- the package already exists
- the package is neither a pure add nor a pure remove
- at least one contained file is `change`

## Reference Rules

References are explicit and method-level.

Rules:

- a reference may be `add`, `change`, or `remove`
- the proposal must not omit a required changed or removed reference
- references are validated using `(source_method, target_method, file_relative_path)`
- reference `change` means signature adaptation only

Endpoint rules:

- a reference `add` is valid only if both endpoint methods already exist or are explicitly proposed in compatible states
- a reference `change` is valid only if both endpoint methods already exist or are explicitly proposed in compatible states
- a reference `remove` is valid only if that reference already exists in the scanned `Project`

Hard rule:

- if a reference is `change`, then the source method must be `change`
- if a reference is `change`, then the target method must be `change`

Reference state expectations:

- if the target method is `remove`, references to that target are expected to be explicitly declared `remove`
- if the target method is `change`, references to that target do not change automatically
- if the target method is `add`, references to that target are expected to be explicitly declared `add`
- a reference may be declared `remove` even when both source and target methods remain otherwise unchanged
- a reference may be declared `change` only when the same source still calls the same target and the callsite adapts to the target signature change

If a target method is declared `change` and a reference to it remains `present`, that means the proposal is asserting that the target changed without requiring caller signature adaptation.

That case is allowed, but it should trigger a warning so the LLM explicitly re-confirms that intent.

Reference identity is still the tuple:

- `(source_method, target_method, file_relative_path)`

`iteration_state` is external to that identity. The identity locates the relationship; the state describes what happens to it in the proposal.

## Touch Rules

Change propagation is directional and state-sensitive.

### Source-Side Rule

If a reference changes, the source side is touched.

This means:

- reference `add` touches the source method
- reference `change` touches the source method
- reference `remove` touches the source method

The touched source method must be declared with a compatible non-`present` state:

- `change`
- `remove`
- `add` if the method itself is new

### Target-Side Rule

The target side is not automatically touched by an incoming reference change.

Example:

- an existing method starts referencing an existing target method
- the source method must be `change`
- the target method may remain unchanged

Example:

- an existing source method removes a reference to a target method that is being removed
- the source method must be `change` or `remove`
- the target method may be `remove`
- the target method is not changed merely because it lost an incoming reference

### Upward Ownership Rule

Touches bubble upward only through ownership:

- changed method touches containing file
- changed file touches containing package

Touches do not bubble sideways across target references.

## Removal Consistency

The UI must not infer removed arrows from removed nodes.

Therefore, the proposal must be explicit.

Rules:

- if a method is `remove`, every existing incoming reference to that method must be explicitly declared `remove`
- if a method is `remove`, every existing outgoing reference from that method must be explicitly declared `remove`
- if a file is `remove`, every existing method in the file must also appear explicitly as `remove`
- if a package is `remove`, every existing file in the package must also appear explicitly as `remove`

Missing declarations are validation errors.

## No UI Inference

The UI renders exactly the merged result it receives.

The UI must not:

- invent removed references
- infer package/file state from method state
- infer method state from changed references
- repair inconsistent input

Consistency is the validator's responsibility.

## Validation Output

Validation returns all detected errors, not just the first one.

Validation may also return warnings when the proposal is structurally valid but semantically ambiguous.

Warnings do not block saving or rendering, but they should be shown to the caller so the LLM or user can reconsider the proposal.

Example shape:

```json
{
  "valid": false,
  "warnings": [
    {
      "code": "signature_change_may_require_reference_change",
      "path": "references[1]",
      "message": "Source and target methods both change while the reference stays present. Confirm that no signature adaptation is required."
    }
  ],
  "errors": [
    {
      "code": "invalid_state_for_existing_method",
      "path": "methods[2]",
      "message": "Existing method 'a.b.c' cannot be proposed with state 'add'."
    },
    {
      "code": "missing_removed_reference",
      "path": "methods[4]",
      "message": "Method 'a.b.d' is marked 'remove' but an outgoing reference was not explicitly declared as 'remove'."
    }
  ]
}
```

The validator should favor stable error codes and precise object paths.

Recommended warning cases:

- method `change` + reference `present` + target `change`
- method `change` + reference `change` + target `change`

These cases are valid, but should prompt the LLM to confirm that the intended meaning is:

- row 35 style: both methods change, but the relationship itself does not need signature adaptation
- row 43 style: both methods change, and the relationship changes because the target signature changed

## Merged Result

After successful validation, the system produces a merged result.

The merged result is a new representation layered on top of `Project`. It is not an in-place mutation of the scanned `Project`.

Merged state meanings:

- `present`: exists in scan and is untouched by the proposal
- `add`: introduced by the proposal
- `change`: exists in scan and is explicitly changed by the proposal
- `remove`: exists in scan and is explicitly removed by the proposal

The merge itself is a service operation, not a first-class domain concept.

The proposal is validated first. After that, the system merges scan truth and proposal into renderable structures that already carry the resolved states.

## Presentation Contract

There is no separate render endpoint that returns a dedicated merged document.

Instead:

- proposals are registered and saved through the proposal endpoint
- the backend loads the active proposal for a project
- the backend merges scan truth and proposal internally
- the UI receives the normal graph payload shape for that project, with changed states and extra proposal notes already embedded

Computation is graph-first:

- proposal application happens at the graph/method-reference level
- file/package diagram information is computed afterward from the graph result
- `Diagram` remains a derived projection

Current presentation decision:

- the changed graph is the same shape as the normal graph
- the difference is in the states carried by the graph elements and any extra proposal metadata attached to them
- the UI does not merge anything itself
- the UI does not infer anything itself

This means:

- there is no separate merged `Project` payload for the UI
- there is no separate merged `DiagramDocument` payload for the UI in this first version
- the UI consumes the graph-shaped payload only
- `iteration_state` lives directly on the graph elements that are rendered

The backend may still use intermediate merged structures internally, but those are not part of the UI contract.

## Proposal Lifecycle

Proposals are ingested through an endpoint.

The LLM is expected to call the proposal endpoint directly and register a saved proposal artifact for a project.

Current product decisions:

- proposals are saved artifacts, not ephemeral previews
- one project may have multiple proposals
- each proposal belongs to one project
- the active default proposal in the UI is the last added proposal for that project
- validation happens on load, on save, and on render
- there is no separate proposal render endpoint in this first version
- proposals are persisted even if they are invalid

The initial product flow is intentionally simple:

1. scan project
2. LLM posts proposal JSON to the proposal endpoint
3. proposal is validated and saved
4. the backend computes the current project SHA using the local git state
5. if the saved proposal SHA does not match the current project SHA, the proposal is rejected for application with an explicit error
6. when the project page is loaded, the backend tries to apply the last added proposal for that project
7. the UI renders the returned graph payload directly

If the latest proposal is invalid or SHA-mismatched:

- the UI shows the explicit error
- the UI stops
- the system does not silently fall back to an older proposal

Selection beyond the default-last-added rule can be added later.

## Rendering Rules

If no `iteration_state` is present in a render object, treat it as `present`.

Colors:

- `present`: current default styling
- `add`: green
- `change`: yellow
- `remove`: red

This applies to:

- packages
- files
- methods
- method-level references
- derived file transitions

Derived transitions inherit state from the method-level references that produce them. The render layer does not invent transition state on its own.

## Worked Examples

### Valid Example: Add New Package/File/Method/Reference

This is valid when each level is declared explicitly:

- package `add`
- file `add`
- method `add`
- reference `add`

### Valid Example: Remove Existing Method And One Outgoing Reference

This is valid when:

- removed method is explicitly `remove`
- removed reference is explicitly `remove`
- containing file is `change` or `remove`
- containing package is `change` or `remove`
- source methods for removed outgoing references are `change` or `remove`

### Invalid Example: Method Remove Without Reference Remove

Invalid when:

- method is `remove`
- related removed incoming/outgoing reference is omitted

### Invalid Example: New Method In Existing File Without File Declaration

Invalid when:

- method is `add`
- containing file is not explicitly declared in the proposal

### Invalid Example: Existing File Declared As Add

Invalid when:

- file already exists in scan truth
- proposal marks it as `add`

## Recommended Service Split

Recommended new components:

- `MergeSpec` model
- `MergeValidator`
- `MergeService`

Responsibilities:

- `MergeSpec`: proposal input model
- `MergeValidator`: structural and semantic validation
- `MergeService`: build merged result after validation

The adapters continue to project the validated merged result into `Diagram` and `Graph`.

## Non-Goals

This spec does not yet define:

- persistence format for saved merge sessions
- comment threads on methods or references
- multi-iteration history
- automated code rewriting

Those can build on top of this merge model later.
