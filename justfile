set shell := ["bash", "-cu"]

default:
    @just --list

# ---- Python --------------------------------------------------------------

lint:
    cd packages/python && uv run ruff check . && uv run ruff format --check .

format:
    cd packages/python && uv run ruff check --fix . && uv run ruff format .

typecheck:
    cd packages/python && uv run mypy src

test:
    cd packages/python && uv run pytest src

build:
    cd packages/python && uv build

# ---- Docs ----------------------------------------------------------------

docs-install:
    cd docs && pnpm install --no-frozen-lockfile

docs-dev:
    cd docs && pnpm run dev

docs-build:
    cd docs && pnpm run build

# ---- CI gates (testing-conventions) --------------------------------------

# Gate: fail if any workflow / composite-action YAML encodes a non-trivial
# inline script (docs/internals/repo.md). Run from the repo root.
gha-lint:
    npx --yes testing-conventions workflow-lint

# ---- Aggregates ----------------------------------------------------------

ci: lint gha-lint typecheck test

hooks:
    pre-commit install --install-hooks

clean:
    rm -rf packages/python/dist docs/.vitepress/dist
