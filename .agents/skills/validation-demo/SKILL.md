---
name: validation-demo
description: Validate and polish this Travel AI Agent repo for portfolio/interview readiness. Use when running backend/frontend checks, adding tests, preparing demo scripts/screenshots, improving README/Docker/.env.example, checking encoding issues, or verifying the project before commit/demo.
---

# Travel Validation Demo

## Overview

Use this skill to produce credible validation evidence and a clean demo story for the Travel AI Agent project.

## Workflow

1. Read `references/demo-checklist.md`.
2. Run the smallest checks that match the change: backend compile, frontend lint/build, focused tests if present.
3. Do not require real API keys for smoke checks; mock external APIs in tests.
4. Verify README and demo notes explain agentic behavior: planner, HITL, tool use, memory/state, guardrails.
5. Report commands run, pass/fail, and untested areas.

## Commands

Use `scripts/check_project.ps1` for a local smoke check when appropriate.

Manual equivalents:

```powershell
python -m compileall src main.py
Set-Location frontend
npm run lint
npm run build
```

## Output Standard

Always summarize:

- Files changed
- Commands run
- Validation result
- Remaining risks or missing checks
