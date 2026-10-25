# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Contributor guide, code of conduct, security policy, issue and pull request
  templates, Dependabot configuration, and `.env.example`.
- Package metadata (project URLs, keywords, classifiers) in `pyproject.toml` and a
  `py.typed` marker for type checkers.

### Changed

- Reorganized the README with a quickstart, architecture diagrams, roadmap, and
  contribution guidance.

## [0.3.0] - 2026-08-17

First public release, built for Hack Hydra Track 03.

### Added

- Eight MCP tools: `remember`, `recall`, `revise`, `timeline`, `trace_memory`,
  `check_conflict`, `explain_trust`, and `forget`.
- Sessionless MCP `2026-07-28` over stdio and stateless Streamable HTTP.
- Contradiction detection, trust decay with a `0.05` floor, and two-hop provenance decay.
- Explicit revisions with `valid_from`/`valid_to` and `SUPERSEDED_BY` edges, plus
  entity timelines.
- Scope-safe evidence tracing through HydraDB's native `algo.SSpaths`.
- Idempotent, retry-safe `remember` writes with durable apply phases.
- React landing page and live HydraDB dashboard, packaged with the Python wheel.
- Six-case Track 03 evaluation, a repeatable stress gate, and a terminal demo.

### Fixed

- Clean-clone installs and dashboard packaging.
- Live test cleanup on populated HydraDB instances.

[Unreleased]: https://github.com/himanshu748/hydramind/commits/main
[0.3.0]: https://github.com/himanshu748/hydramind/commits/main
