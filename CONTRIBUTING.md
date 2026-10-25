# Contributing to HydraMind

Thanks for helping. HydraMind aims to be a small, honest, well-tested memory layer
for coding agents, and every contribution counts: bug reports, docs, tests, UI
polish, and new retrieval ideas.

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Contents

- [Ways to contribute](#ways-to-contribute)
- [Development setup](#development-setup)
- [Running checks](#running-checks)
- [Workflow](#workflow)
- [Coding standards](#coding-standards)
- [Testing guidelines](#testing-guidelines)
- [UI development](#ui-development)
- [Documentation](#documentation)
- [Releasing](#releasing)
- [Getting help](#getting-help)

## Ways to contribute

- **Report a bug** with the [bug report form](https://github.com/himanshu748/hydramind/issues/new?template=bug_report.yml).
- **Suggest a feature** with the [feature request form](https://github.com/himanshu748/hydramind/issues/new?template=feature_request.yml).
- **Pick up an issue.** Issues labelled `good first issue` or `help wanted` are good
  starting points. Comment on the issue so nobody duplicates the work.
- **Improve docs.** Clearer setup steps and host guides are always welcome.
- **Work on the [roadmap](README.md#-roadmap).** For larger changes, open an issue
  first to agree on the design before you write a lot of code.

Security issues follow a separate, private process. See [SECURITY.md](SECURITY.md).

## Development setup

You need:

- Linux or macOS (Windows is not supported yet)
- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/) (recommended), or `pip`
- Node.js 22 and npm, only for UI changes
- A source-built HydraDB `graph-node`, only for the live integration tests.
  Docker is not required. See
  [HydraDB's local server instructions](https://github.com/hydra-db/hydradb#run-a-local-server).

```bash
# Fork on GitHub, then:
git clone https://github.com/<your-username>/hydramind.git
cd hydramind
git remote add upstream https://github.com/himanshu748/hydramind.git

uv sync --extra dev --locked
```

To run the live suite, export the same token that `graph-node` reads from
`GRAPH_AUTH_TOKEN_FILE`:

```bash
cp .env.example .env      # edit values, never commit .env
set -a; . ./.env; set +a
```

## Running checks

These match [CI](.github/workflows/ci.yml). Run them before you push:

```bash
uv run ruff check src tests examples
uv run ruff format --check src tests examples
uv run mypy src
uv run pytest -m 'not integration'
```

If you have HydraDB running, also run the full suite and the evaluation:

```bash
uv run pytest
uv run python -m benchmarks.track03_eval
```

Run `uv run ruff format src tests examples` to fix formatting automatically.

## Workflow

1. Sync with upstream and create a branch from `main`:
   ```bash
   git fetch upstream && git checkout -b feat/short-description upstream/main
   ```
   Prefixes such as `feat/`, `fix/`, `docs/`, `test/`, and `refactor/` help reviewers.
2. Make focused commits. Write messages in the imperative mood and describe the
   effect, for example `Bound trace overfetch per scope`.
3. Add or update tests and docs alongside the code.
4. Add a line under **Unreleased** in [CHANGELOG.md](CHANGELOG.md) for user-visible changes.
5. Push and open a pull request. Fill in the template, link the issue
   (`Closes #123`), and say which checks you ran, including whether you ran the live suite.
6. Address review feedback with new commits. The maintainer may squash on merge.

Keep pull requests small. Several small PRs are reviewed faster than one large one.

## Coding standards

- **Python:** formatted and linted by Ruff (line length 100, rules `E F I UP B SIM`)
  and type-checked with `mypy --strict`. Fully type public functions.
- **Stay inside HydraDB's surface.** Queries must stay within the documented
  [Cypher compatibility surface](https://github.com/hydra-db/hydradb/blob/main/cypher-compat.md).
  The Bolt runtime is auto-commit only and has no `CREATE CONSTRAINT`.
- **Scope everything.** Every query and direct-ID tool must enforce the caller's
  scope. Never let data cross scopes.
- **Preserve history.** Memory operations must never silently delete provenance.
  Contradictions, revisions, and decay are recorded as graph data.
- **Keep the abstention guarantee.** Recall must keep returning `[]` when evidence is
  insufficient. Retrieval changes need positive and hard-negative tests.
- **Stdout belongs to MCP.** In the stdio server, log to stderr only.
- **Dependencies:** avoid new runtime dependencies unless clearly justified. Update
  `uv.lock` with `uv lock` when `pyproject.toml` changes.
- **Comments:** explain why, not what.

## Testing guidelines

- Tests live in `tests/` and run with pytest.
- Mark any test that needs a live Bolt endpoint with `@pytest.mark.integration` so the
  database-independent subset keeps working in CI.
- Prefer real behavior over mocks. Existing live tests use isolated scopes and clean
  up after themselves. Follow the same pattern.
- Bug fixes should include a regression test that fails without the fix.
- If you change the evaluation or stress numbers quoted in the README, regenerate the
  checked-in results in `benchmarks/results/` and say so in the PR.

## UI development

The dashboard lives in `ui/` (React, Vite, TypeScript). The built output in `ui/dist`
is committed so the Python package works without Node, and CI fails if `ui/dist` does
not match a fresh build.

```bash
cd ui
npm ci
npm run dev       # Vite dev server
npm run build     # required before committing UI changes
```

Run `.venv/bin/hydramind-ui` to serve the built UI against a live HydraDB. Commit the
regenerated `ui/dist` with your source changes. Visual work must follow
[design.md](design.md): responsive from 360px to 1440px, accessible controls,
visible focus, and reduced-motion support. Include before and after screenshots in
UI pull requests.

## Documentation

- Update [README.md](README.md) when behavior, configuration, or commands change.
- Keep claims measurable and honest. Say what was run and where, and avoid
  unqualified performance claims.
- New environment variables go in the README configuration table and in `.env.example`.

## Releasing

Maintainers only:

1. Update the version in `pyproject.toml` and `ui/package.json`.
2. Move **Unreleased** entries in `CHANGELOG.md` under the new version and date.
3. Rebuild the UI and run the full suite, including the live tests.
4. Tag `vX.Y.Z`, push the tag, and publish a GitHub release with the changelog notes.

## Getting help

Open an [issue](https://github.com/himanshu748/hydramind/issues) with your question.
Include your OS, Python version, HydraDB commit, and what you tried.

Thank you for making HydraMind better! 🐉
