---
id: 83
uid: 8277a65d-14da-4db5-b45a-eadb2d355435
title: Leave room for the squash suffix in commit subjects
type: chore
status: done
milestone: v0.3.1
assignee: Oddur Sigurdsson
created: 2026-11-02
updated: 2026-11-02
closed_at: 2026-11-02
priority: p3
effort: s
area: tooling
---

## Problem

Found by the review of v0.1–v0.3 on 2026-11-02. GitHub appends " (#N)" to the squash subject, so eight subjects on main are longer
than the 72-character limit the hooks enforce on the branch.

## Acceptance criteria

- [x] The commit-msg hook and scripts/attribution cap subjects so that the squash subject, suffix included, stays within 72 (test)

## Result

commit-msg caps subjects at 64 characters, so the squash subject with " (#N)" stays within 72; tested, and CONTRIBUTING.md and AGENTS.md say why.
