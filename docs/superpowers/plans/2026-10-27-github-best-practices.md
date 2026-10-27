# GitHub Best Practices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (inline execution selected) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GitHub repository and branch governance are hardened without requiring pull-request reviews, and all existing pull requests are validated and merged.

**Architecture:** Versioned repository guidance lives in `.github/`; GitHub-side merge, security, and feature settings are applied through the repository API. Existing workflows remain the required CI source of truth.

**Tech Stack:** GitHub CLI/API, GitHub Actions, Markdown, YAML.

## Global Constraints

- No required pull-request reviews.
- No application-runtime changes.
- Keep existing SHA-pinned GitHub Actions.
- Require existing CI checks before merging.
- Do not merge a PR until its current checks are green and it is mergeable.

---

### Task 1: Add repository governance documents

**Files:**
- Create: `.github/CODEOWNERS`
- Create: `.github/pull_request_template.md`
- Create: `SECURITY.md`

- [ ] Add the repository owner as the default code owner without making owner approval a required branch rule.
- [ ] Add a concise PR checklist covering scope, tests, security impact, and documentation.
- [ ] Document supported versions, private vulnerability reporting, and the prohibition on public vulnerability disclosure before coordination.
- [ ] Run `git diff --check`.
- [ ] Commit the governance documents.

### Task 2: Harden versioned GitHub configuration

**Files:**
- Modify: `.github/workflows/build.yaml`
- Modify: `.github/workflows/repository-checks.yaml`
- Modify: `.github/workflows/zizmor.yaml`
- Modify: `.github/workflows/update-litellm.yaml`
- Modify: `.github/dependabot.yaml`

- [ ] Add explicit job timeouts where existing workflows can wait or build for a long time.
- [ ] Preserve minimal `permissions` and SHA-pinned actions.
- [ ] Keep Dependabot updates grouped by their existing ecosystems and bounded open-PR counts.
- [ ] Run actionlint-equivalent syntax checks available locally plus repository tests.
- [ ] Commit the workflow/configuration changes.

### Task 3: Configure GitHub repository governance

**Files:**
- External: repository settings for `rosch100/haos-litellm`
- External: branch protection for `main`

- [ ] Keep squash merging enabled and disable merge commits and rebase merges.
- [ ] Keep automatic branch deletion and auto-merge enabled.
- [ ] Enable secret-scanning non-provider patterns and preserve push protection.
- [ ] Disable unused Wiki and Projects features.
- [ ] Require pull requests, current required status checks, conversation resolution, linear history, and no force-push/deletion on `main`.
- [ ] Configure zero required reviews explicitly.
- [ ] Re-read the settings and protection response as verification.

### Task 4: Fix, verify, and merge all open pull requests

**Files:**
- External: all currently open pull requests

- [ ] Refresh each PR's head, mergeability, comments, and checks.
- [ ] Fix only concrete conflicts, unresolved comments, or failing checks within scope.
- [ ] Re-run scoped local checks for every code change.
- [ ] Merge each PR only after a fresh green status and mergeable state.
- [ ] Re-list open PRs and confirm the requested set is empty.

