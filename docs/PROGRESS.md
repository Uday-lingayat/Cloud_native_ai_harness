# PROGRESS.md: Living status (update at the end of EVERY session)

## Current state

- **Current phase:** Phase 1
- **Current milestone:** 1.0 Project skeleton
- **Status:** Not started
- **Last updated:** (date)
- **Does `make test` pass?** n/a

## What works right now

Nothing yet. (Replace this with a short list, for example "sandbox can run pytest in a container".)

## Next step

Start milestone 1.0 in `docs/PLAN.md`: create the project skeleton, Makefile, and tooling config.

## Known issues / open questions

- None yet.

## How to run the current demo

(Fill in once something runs, with the exact commands and expected output.)

## Environment notes

- LLM provider: set via `.env` (`LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`; see `.env.example` and D-14).
  The user plans to use Gemini via Google AI Pro developer credits (needs activation and a Cloud billing account) and `MockLLM` for most development.
- Before the first real LLM call: confirm the user has set a provider budget alert.
- Docker required locally. Benchmarks should run on Linux (cloud VM), not Docker Desktop.

---

## Session log (newest first, one entry per session)

### Template
```
### YYYY-MM-DD
- Did: ...
- Milestones completed: ...
- Tests: passing / failing (details)
- Decisions made: (also record in DECISIONS.md)
- Left off at: ...
- Next: ...
```

### (no sessions yet)

---

## Note on optional work

Milestones marked "(Optional)" in PLAN.md (4.3, 4.5a, 4.5b, 4.6) are done only after all
non-optional Phase 4 milestones, and only if the user confirms. Do not start them earlier.
