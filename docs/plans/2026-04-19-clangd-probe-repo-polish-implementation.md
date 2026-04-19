# clangd-probe Repository Polish Implementation Plan

> **For Claude:** REQUIRED EXECUTION SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add the minimal repository-level files and GitHub metadata needed to make `clangd-probe` look complete as a standalone open source CLI project.

**Architecture:** Keep the implementation small and documentation-focused: add `LICENSE`, add a short `CONTRIBUTING.md`, then use `gh` to populate GitHub repository description and topics. No CLI behavior changes.

**Tech Stack:** Markdown, standard MIT license text, GitHub CLI.

---

### Task 1: Add repository files

**Files:**
- Create: `LICENSE`
- Create: `CONTRIBUTING.md`

**Step 1: Add MIT license**

Create a standard MIT license file.

**Step 2: Add minimal contributor guide**

Document:

- local editable install
- core pytest command
- expectation to keep docs and skill aligned with behavior
- expectation to prefer `--json` for automation examples

### Task 2: Set GitHub metadata

**Files:**
- Verify only

**Step 1: Set description**

Use `gh` to set:

`Agent-friendly CLI wrapper around clangd for shell-based semantic navigation`

**Step 2: Set topics**

Use `gh` to add:

- `clangd`
- `cli`
- `lsp`
- `cxx`
- `developer-tools`
- `automation`

### Task 3: Verify and publish

**Files:**
- Verify only

**Step 1: Re-check repository metadata**

Use `gh repo view ... --json ...` to confirm description and topics.

**Step 2: Commit and push**

Commit the new files and push to `origin/main`.
