---
title: "Cosmos Local Dev/Public Contract"
summary: "Repo-local remotes, paths, and standing overrides for cosmos-dev vs public cosmos."
tags: [docs, migration, release]
date: 2026-04-17
lastmod: 2026-08-03
---

# Purpose

This page is intentionally narrow. The canonical dev/public parity posture for
Polli split repos lives in the org-level `polli-dev-conventions` skill,
`references/release-ritual.md` in `agents-infra`.

Use this page only for Cosmos-specific local surfaces, remotes, and standing
overrides. Do not duplicate org-level promotion policy here.

# Local surfaces

- private integration clone: `~/dev/cosmos/dev`
- private worktrees: `~/dev/cosmos/wt/<branch>`
- public inspection/release clone: `~/dev/cosmos/public/cosmos`

# Remote contract

In the private integration clone:

- `origin` => `polli-labs/cosmos-dev`
- `public` => `polli-labs/cosmos`

# Standing local overrides

- Public inspection/release clone: `~/dev/cosmos/public/cosmos`
- No standing private-only package, SDK, documentation, dependency, or lockfile
  exceptions are recorded today.

The public-owned exception set is closed and contains exactly these four paths:

| Path | Public ownership reason |
|---|---|
| `AGENTS.md` | Public-repository instructions must not expose or inherit the private `cosmos-dev` worktree guide. |
| `.github/workflows/codeql.yml` | GitHub security analysis belongs to the public repository's security surface. |
| `.github/workflows/docs.yml` | Public documentation deployment and its credentials belong to the public release surface. |
| `.github/workflows/publish.yml` | Tag-triggered package publication and release credentials belong to the public release surface. |

Everything not listed above is public-safe by default and should converge through
the audited promotion path. Any additional divergent path is unclassified drift,
not an implicit exception.

# Supply-chain release posture

Cosmos follows the shared Polli Python supply-chain posture without a
repo-specific exception:

- Private `.github/workflows/ci.yml` and the public-owned docs/release jobs sync
  from the committed `uv.lock` with `uv sync --locked`, then execute tools with
  `uv run`.
- `pyproject.toml` carries a uv resolver cooldown so new packages age before
  routine lock refreshes pick them up.
- Release build/check tools are declared as the project `release` extra instead
  of being resolved live in the public-owned publish workflow.
- The private `cosmos-dev` repository remains the review source of truth; the
  public `cosmos` repository is the release surface for public-safe changes.

The public-owned publish workflow currently uses token-based Twine environment
variables for PyPI and TestPyPI. Moving it to trusted publishing or OIDC is a
separate public release-infrastructure change because it changes repository and
package-index credentials rather than only dependency resolution.
