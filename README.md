# Panalyzer

Panalyzer analyzes a Python codebase and turns it into a navigable architecture map.

It is built for two related workflows:

- export a machine-readable architecture document as JSON
- open a web app to inspect package, file, and method relationships visually

The current UI is especially useful for understanding:

- packages and files in a project
- methods defined in each file
- internal call relationships
- file-to-file transitions aggregated from method calls

## What It Produces

Panalyzer works in two modes.

### 1. CLI JSON Export

Running `panalyzer` on a project prints a canonical architecture JSON document to stdout.

That JSON includes:

- `summary`
- `sections`
- `nodes`
- `edges`

This output is meant to be readable by both humans and LLM-based tooling.

### 2. Web App

The web app lets you:

- save project roots in `app.yaml`
- import a public Git repository over `https://`
- open a project as an interactive graph
- switch between:
  - `Files`: package -> file view with aggregated file-to-file transitions
  - `Methods`: package -> file -> method view with method-level edges

## Installation

From the repo root:

```bash
./install.sh
```

If the installed command is not on your `PATH`, add:

```bash
export PATH="/home/rawsteel/.local/bin:$PATH"
```

## Usage

### Analyze Current Directory

```bash
panalyzer
```

### Analyze a Specific Project

```bash
panalyzer /path/to/project
```

### Start the Web App

```bash
panalyzer start
```

Default address:

```text
http://127.0.0.1:7000
```

The app now binds to `0.0.0.0:7000` by default, so `127.0.0.1:7000` works locally and the same server can be exposed by a container or hosting platform.

If `app.toml` already exists, Panalyzer will migrate it to `app.yaml` on first startup.

### Check Status

```bash
panalyzer status
```

### Stop the Web App

```bash
panalyzer stop
```

## Config Files

Panalyzer uses two separate config files.

### `app.yaml`

This controls the web app runtime and saved projects.

Example:

```yaml
server:
  host: 0.0.0.0
  port: 7000
projects:
  - name: my-project
    path: /absolute/path/to/project
  - name: another-project
    path: /workspace/.panalyzer-projects/another-project-abc123
    source: https://github.com/org/another-project.git
```

### `panalyzer.toml`

This controls per-project analysis behavior.

Example:

```toml
[analyzer]
source_roots = ["src"]
include_external_references = false
ignore_files = ["__init__.py"]
```

Notes:

- `source_roots` tells Panalyzer which directories should be treated as Python source roots
- `include_external_references = false` keeps the graph focused on project-internal relationships
- `ignore_files` uses glob-style patterns

## JSON Shape

The CLI emits a canonical architecture document with stable identifiers.

Top-level structure:

```json
{
  "root": "/path/to/project",
  "summary": {},
  "sections": [],
  "nodes": [],
  "edges": []
}
```

In practice:

- `sections` provide grouped package/file structure
- `nodes` contain package, file, and method nodes
- `edges` contain internal call relationships

## Web UI Behavior

The default project view opens in `Files` mode.

The add-project form accepts either:

- an absolute local path
- an `https://` Git repository URL

Views:

- `Files`
  - hides methods
  - collapses repeated method calls into one file-to-file edge
- `Methods`
  - shows package -> file -> method structure
  - shows method-level internal call edges

## Current Scope

Panalyzer is currently focused on Python projects and static AST analysis.

It handles:

- package grouping
- file discovery
- function/method/class discovery
- internal reference tracking
- relative import resolution
- grouped interactive visualization

## Limitations

Current limitations are mostly the usual static-analysis ones:

- dynamic dispatch is not fully resolved
- complex runtime import behavior is not fully resolved
- external/library calls are excluded by default
- large graphs can still become visually dense, especially in method view
- public repo import shells out to `git clone`, so hosted deployments still need `git` installed

## Deployment

For a hosted deployment, run the foreground web server entrypoint instead of the background `panalyzer start` helper:

```bash
panalyzer-web --config ./app.yaml
```

Most platforms provide a `PORT` environment variable. Panalyzer will honor that automatically.

Minimum deployment requirements:

- Python 3.11+
- `git` available on the runtime image
- writable storage for `app.yaml`, `.panalyzer-runtime.json`, logs, and `.panalyzer-projects/`

Recommended pattern:

```bash
pip install .
panalyzer-web --config /app/app.yaml
```

## Development

Useful commands:

```bash
python -m compileall -q src
./install.sh
```

The installed entrypoint is defined in [pyproject.toml](./pyproject.toml).
