# ADR-002 — Per-module package layout convention

- **Status:** Accepted

## Context

The repository grew to ~47 Django apps sharing one GraphQL schema. Without a common
structure, adding a feature meant guessing where models, resolvers and types live.

## Decision

Every feature module under `lipaidox/<module>/` follows the same layout:

```
models/       # one file per model, re-exported in __init__.py
queries/      # @strawberry.type Query class with resolvers
mutations/    # @strawberry.type Mutation class
schema/       # strawberry types for the module
migrations/
```

Register the app in `INSTALLED_APPS` and mix its Query/Mutation classes into the root
schema (ADR-001). The LMS modules follow the same pattern with `queries/`/`mutations/`
packages exporting their class sets.

## Consequences

- (+) New modules are cheap to scaffold and inspect; conventions are discoverable.
- (+) Resolver/RBAC placement is uniform across domains.
- (-) The pattern is enforced socially, not by tooling (no linter enforces it yet).
- (-) A few modules drifted (flat `models.py`, `discover/` empty, `media_processor`
  outside `lipaidox/`); a cleanup pass is needed.