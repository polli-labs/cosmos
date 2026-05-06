---
title: "Cosmos Local Dev/Public Contract"
summary: "Repo-local remotes, paths, and standing overrides for cosmos-dev vs public cosmos."
tags: [docs, migration, release]
date: 2026-04-17
lastmod: 2026-05-06
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
- Public-owned instruction exception: public `AGENTS.md` stays public-safe and
  does not mirror the private `cosmos-dev` worktree guide.
- Public-owned security workflow exception: public `.github/workflows/codeql.yml`
  is owned by the public repository's GitHub security surface and does not
  need to exist in `cosmos-dev`.
- No package, SDK, docs, dependency, lockfile, CI, docs-build, or publish
  workflow private-only exceptions are recorded here today.
- Keep this page limited to local paths, remotes, and explicit long-lived
  overrides when they exist.

# Supply-chain release posture

Cosmos follows the shared Polli Python supply-chain posture without a
repo-specific exception:

- CI, docs, and release jobs sync from the committed `uv.lock` with
  `uv sync --locked`, then execute tools with `uv run`.
- `pyproject.toml` carries a uv resolver cooldown so new packages age before
  routine lock refreshes pick them up.
- Release build/check tools are declared as the project `release` extra instead
  of being resolved live in the publish workflow.
- The private `cosmos-dev` repository remains the review source of truth; the
  public `cosmos` repository is the release surface for public-safe changes.

Current intentional follow-up: PyPI and TestPyPI publishing still use the
existing token-based Twine environment variables. Moving to trusted publishing
or OIDC should be a separate release-infrastructure change because it changes
repository and package-index credentials rather than only dependency
resolution.
