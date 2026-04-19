# clangd-probe Repository Polish Design

## Goal

Prepare the standalone `clangd-probe` repository for public use by filling in
the minimal repository-level items that users expect from an open source CLI
project.

## Problem

The code, tests, README, and skill are already in good shape, but the
repository itself still looks incomplete:

- no license file
- no contributor guidance
- empty GitHub description and topics

That makes the project harder to evaluate and reuse, even though the actual CLI
is ready.

## Chosen Approach

Add the smallest useful set of repository-level polish:

- add an MIT `LICENSE`
- add a short `CONTRIBUTING.md`
- set GitHub repository description and topics with `gh`

Keep this pass intentionally small. Do not widen into release automation,
homepage hosting, changelog systems, or other non-essential project scaffolding.

## Boundaries

- no behavior changes to the CLI
- no packaging changes beyond repository metadata and documentation
- no heavy contributor policy documents

## Validation

This work is complete when:

- the repository has a license file
- the repository has a short contributor guide
- GitHub shows a non-empty description and useful topics
- the working tree is clean after commit and push
