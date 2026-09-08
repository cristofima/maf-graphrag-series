<!--
Title format: <type>(<scope>): <description> — see .github/skills/commit-message-writing/SKILL.md
for the Conventional Commits type list and this repo's canonical scopes.
-->

## Summary

<!-- One or two sentences: what does this PR do, and why now? -->

## Motivation

<!-- Root cause, prior gap, or context a reviewer needs before reading the diff.
     Link related issues/discussions. Don't assume familiarity with the history. -->

Closes #

## What changed

<!-- Bullet per logical change. Pair the action with its purpose/effect —
     "Add X" alone is not enough; say why. Name the specific
     module/function/file when it's the clearest way to describe it. -->

-

## Testing

<!-- Commands you ran and their result. Mark anything not covered. -->

- [ ] `uv run pytest` — full suite passes
- [ ] `uv run ruff check src tests` / `uv run ruff format --check src tests` — clean
- [ ] `uv run python -m mypy src/maf_graphrag/... --ignore-missing-imports --no-error-summary` — clean (if `src/` changed)
- [ ] No live Azure OpenAI / Foundry evaluation calls were made unintentionally while validating locally

## Router contract impact (delete this section if not applicable)

- [ ] `classified_workflow`, `routed_workflow`, `classifier_status`, `classifier_attempts`, and `fallback_reason` metadata fields are preserved
- [ ] Confidence threshold (`>= 80`) and fallback-to-`sequential` behavior are unchanged, or the change is called out explicitly above
- [ ] Router-focused tests updated: `tests/workflows/test_router.py`, `tests/agents/test_router_classifier.py`

## Screenshots (delete this section if not applicable)

<!-- DevUI, Microsoft 365 Agents Playground, or Foundry evaluation/redteam dashboard evidence. -->

## Notes for reviewers

<!-- Anything you want specific feedback on (design, naming, test coverage),
     and anything intentionally deferred/out of scope for this PR. -->
