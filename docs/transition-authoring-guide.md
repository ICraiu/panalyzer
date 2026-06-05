# Transition Authoring Guide

This document explains how to author method-level reference transitions in a proposal.

## Core Rule

A transition is always a method-level reference:

- source method
- target method
- file-relative path where the call appears

Transitions are never declared at file level or package level.

## Transition States

Transitions use these states:

- `add`
- `change`
- `remove`

`present` is never authored in proposal input.

## Meanings

### `add`

Use `add` when:

- the source method starts calling the target method
- the source-target relationship did not exist before

Examples:

- new method calls an existing method
- existing method starts calling a new method
- existing method starts calling another existing method for the first time

### `remove`

Use `remove` when:

- an existing source method stops calling an existing target method
- a removed source method drops its outgoing calls
- a removed target method causes incoming references to disappear

`remove` may be used even if the source or target method otherwise remains unchanged.

### `change`

Use `change` only for one case:

- the same source method still calls the same target method
- the relationship remains
- the callsite changes because the target signature changed

This is the only meaning of transition `change` in the current model.

Do not use transition `change` for generic behavioral rewrites.

If the source changes internal behavior but still calls the target in the same compatible way, keep the transition unchanged.

## When To Warn

These combinations are valid but should trigger warnings:

### Row 35

- source = `change`
- transition = `present`
- target = `change`

Meaning:

- both methods changed
- the relationship stayed the same

Warning reason:

- confirm that the target change does not require callsite adaptation

### Row 43

- source = `change`
- transition = `change`
- target = `change`

Meaning:

- the target changed
- the source changed
- the relationship changed because the source adapted to the target signature

Warning reason:

- confirm that this is really a signature-adaptation relationship, not some broader behavioral rewrite

## Quick Rules

- if the source starts calling the target: `add`
- if the source stops calling the target: `remove`
- if the same call remains but adapts to target signature change: `change`

If none of these apply, do not author a transition entry.
