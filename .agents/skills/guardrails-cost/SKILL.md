---
name: guardrails-cost
description: Add production guardrails to this Travel AI Agent repo. Use when implementing out-of-scope detection, safe refusals, cost controls, tool budgets, rate limits, caching, abuse/spam handling, API key fallbacks, or audit logging before expensive LLM/tool execution.
---

# Travel Guardrails Cost

## Overview

Use this skill to prevent unrelated or abusive prompts from consuming LLM/tool budget and to make expensive travel workflows observable and bounded.

## Workflow

1. Read `references/guardrails-policy.md`.
2. Place cheap scope checks before planner/supervisor/tool execution.
3. Route `travel` to planner, valid `follow_up` to current trip/session, `chitchat` to short answer, and `out_of_scope` to safe refusal.
4. Track tool usage per session/trip before calling external APIs.
5. Cache repeated external API requests with keys based on tool name and normalized query parameters.
6. Log guardrail decisions with session id, intent, reason, and whether tools were blocked.

## Defaults

- Out-of-scope responses must not call search, flight, hotel, weather, planner, or supervisor.
- Tool-heavy repeated searches should require confirmation or be blocked after budget.
- Cache TTL defaults: flight/hotel 10-30 minutes, weather 1-3 hours, destination info 24 hours.
- If API keys are missing, return a user-facing limitation message and keep the app running.

## Validation

Test guardrails with prompts for travel, follow-up, chitchat, out-of-scope, repeated search, and missing API key behavior. Use mocks for external tools.
