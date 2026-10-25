# Architecture

posix-tools is a pure-Python library of APIs that wrap native POSIX tools. It imports only the standard library.

## Packages

```
packages/
  python/    the `posix-tools` package (hatchling, src layout).
docs/        VitePress site (published to GitHub Pages).
  internals/ contributor + agent conventions (not published).
```

## Release flow

`putitoutthere.toml` declares the one PyPI artifact. The `Release` workflow (`.github/workflows/release.yml`) calls the reusable workflow at `thekevinscott/putitoutthere`. The version comes from git tags via `hatch-vcs`.

## CI gates

- [`python.yml`](.github/workflows/python.yml) runs lint, typecheck, and unit tests.
- [`conventions.yml`](.github/workflows/conventions.yml) calls the upstream [testing-conventions workflow](https://github.com/thekevinscott/testing-conventions/blob/v0/.github/workflows/testing-conventions.yml) at `v0` against `packages/python`, with upstream defaults.
- `changelog.yml` runs the upstream testing-conventions `changelog` gate: a fragment under `docs/changelog.d/` on PRs that touch package code, plus `docs/migrations.d/` when a commit carries a `breaking:` trailer.
- `workflow-lint.yml` runs the upstream testing-conventions `workflow-lint` gate, which fails on logic inlined in workflow YAML.
- `build-check.yml` and `check.yml` validate the release build and `putitoutthere.toml` on PRs.
- `docs.yml` builds + deploys the VitePress site.
- `pr-monitor.yml` gates merge on the aggregate CI status.

## Public-API surface

Defined in `docs/internals/repo.md`: every exported value/type, every config key, every observable artifact. Changes to that surface require a fragment under `docs/changelog.d/` (plus `docs/migrations.d/` when breaking).
