# Proposal Flow Guide

This guide explains how to test Panalyzer's current proposal flow end to end.

It covers:

1. extract the current architecture
2. author a proposal in the supported JSON format
3. submit the proposal to the running app
4. verify the merged result

This reflects the current implementation, not a future UI.

## Current Status

The proposal flow is testable now.

What exists today:

- architecture extraction through the CLI
- proposal validation and persistence
- proposal application to the graph view
- blocking errors for invalid proposals or SHA mismatches
- proposal warnings surfaced in the project graph UI

What does not exist yet:

- proposal upload form in the web UI
- proposal list/selection UI
- explicit `normal` / `proposal` / `focused` architecture mode switch

So the current practical workflow is:

- use the CLI to inspect architecture
- create proposal JSON
- submit it through the proposal endpoint
- open the project page and inspect the merged graph

## Files To Read First

Before writing proposals, read these two documents:

- [merge-spec.md](/home/rawsteel/repo/panalyzer/docs/merge-spec.md:1)
- [transition-authoring-guide.md](/home/rawsteel/repo/panalyzer/docs/transition-authoring-guide.md:1)

Use them as the source of truth for:

- valid proposal object identities
- allowed states
- parent-child declaration rules
- reference transition semantics

## Step 1: Start The App

If the app is not running:

```bash
panalyzer start
```

If you want to be sure you are on the latest installed code:

```bash
./restart.sh
```

The default web app URL is:

```text
http://127.0.0.1:7000
```

## Step 2: Register The Target Project

Open the homepage and add the target repository path.

Example:

```text
/absolute/path/to/target-repo
```

After saving, open the project page in the browser.

The URL will look like:

```text
http://127.0.0.1:7000/projects/<project_id>
```

You will need that `project_id` when submitting a proposal.

## Step 3: Extract The Current Architecture

Panalyzer supports two CLI views.

### Default Architecture View

This is the file-level architecture diagram and is the normal input surface for proposal work.

```bash
panalyzer /absolute/path/to/target-repo
```

This returns JSON shaped like:

- `root`
- `summary`
- `packages`
- `files`
- `transitions`

Use this when you want to understand:

- packages
- files
- file-to-file transitions derived from method references

### Full Scan View

Use this when you need the raw method/reference layer.

```bash
panalyzer -a /absolute/path/to/target-repo
```

This returns the full scan model, including:

- packages
- files
- methods
- method-level references

Use this when the LLM needs exact method identities such as:

- method `qualname`
- containing file
- authored references

## Step 4: Get The Current Project SHA

Each proposal is pinned to a git SHA.

Get it from the target repository:

```bash
git -C /absolute/path/to/target-repo rev-parse HEAD
```

That value must be used as `project_sha` in the proposal.

If the repository moves to another commit before the proposal is applied, Panalyzer will reject it for application.

## Step 5: Author The Proposal JSON

Proposal input is explicit.

The LLM must declare:

- packages
- files
- methods
- references

It must not rely on Panalyzer to infer missing declarations.

Proposal states are:

- `add`
- `change`
- `remove`

`present` is not allowed in proposal input.

### Minimal Example

```json
{
  "id": "proposal_001",
  "name": "Extract merge validation service",
  "created_at": "2026-06-06T10:30:00Z",
  "author": "codex",
  "source_model": "gpt-5",
  "rationale": "Move merge validation into a dedicated service.",
  "project_sha": "PUT_REAL_SHA_HERE",
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
      "source_method": "project_analyzer.cli.analyze_path",
      "target_method": "project_analyzer.merge.service.apply_merge",
      "file_relative_path": "src/project_analyzer/cli.py",
      "iteration_state": "add"
    }
  ]
}
```

## Step 6: Submit The Proposal

Today, proposal submission is API-based.

Save the JSON to a file, for example:

```text
/tmp/proposal.json
```

Then submit it:

```bash
curl -sS \
  -X POST \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/proposal.json \
  http://127.0.0.1:7000/projects/<project_id>/proposals
```

### Response Semantics

`201 Created`

- proposal is valid
- proposal was saved

`202 Accepted`

- proposal was saved
- validation returned errors and/or warnings
- invalid proposals are still persisted

`400 Bad Request`

- request body is not valid JSON

The response body contains:

- `proposal`
- `validation.valid`
- `validation.warnings`
- `validation.errors`

## Step 7: Read Validation Output

Panalyzer validates the proposal against:

- the current scanned `Project`
- parent-child explicitness rules
- reference transition rules
- current git SHA

### Blocking Errors

Examples:

- object declared with the wrong state for existence
- missing parent package/file declaration
- missing explicit removed references
- project SHA mismatch

If the latest proposal is invalid, the project graph page will show an explicit error and stop.

Panalyzer does not silently fall back to an older proposal.

### Warnings

Warnings do not block saving or rendering.

They are used for structurally valid but semantically questionable cases, especially around:

- target method changes without caller adaptation
- reference `change` meaning signature adaptation

The LLM should be instructed to treat warnings as “review this carefully”.

## Step 8: Verify The Merged Result

Open the project page again:

```text
http://127.0.0.1:7000/projects/<project_id>
```

Current behavior:

- if there is no saved proposal, you see the normal architecture
- if the latest proposal is valid and SHA-matched, you see the merged graph
- if the latest proposal is invalid or SHA-mismatched, you see a blocking error

Proposal state is rendered directly on graph elements:

- `present`
- `add`
- `change`
- `remove`

Current visual interpretation:

- `add` elements are green
- `change` elements are yellow
- `remove` elements are red

## Recommended LLM Workflow

Use this sequence:

1. extract architecture with `panalyzer <path>`
2. inspect exact methods and references with `panalyzer -a <path>` if needed
3. get current `project_sha`
4. ask the LLM to produce proposal JSON that conforms to:
   - [merge-spec.md](/home/rawsteel/repo/panalyzer/docs/merge-spec.md:1)
   - [transition-authoring-guide.md](/home/rawsteel/repo/panalyzer/docs/transition-authoring-guide.md:1)
5. submit the proposal
6. inspect validation output
7. open the project page and review the merged graph

## Good Prompting Rules For The LLM

When asking the LLM to author a proposal, tell it:

- proposals must be explicit
- do not use `present`
- declare packages, files, methods, and references directly
- use project-relative file paths
- use exact method `qualname` values from the extracted architecture
- reference `change` means signature adaptation only

## Current Limitations

These are known current limitations of the product flow:

- proposal submission is API-only
- latest proposal auto-application is the only proposal selection behavior
- there is no explicit compare mode yet
- there is no proposal-only focused mode yet

Those are UI/product limitations, not backend validation limitations.

## Practical Testing Recommendation

Start with small proposals:

- add one file and one method
- remove one reference
- change one method plus one adapting reference

Do not begin with a large repo-wide rewrite proposal.

That will make it easier to verify:

- the proposal shape
- the validation output
- the merged graph rendering
