# AGENTS.md: Read this first, every session

You are a coding agent building **CodeHarness**: a platform that runs AI coding agents
in isolated Docker sandboxes, orchestrates many in parallel, and streams their work
live to a React dashboard. This is a resume/portfolio MVP for an AI + Python backend role.

You may be resuming after days or weeks. You have no memory of earlier sessions.
**These files are your memory.** Trust them over your assumptions.

## Session start routine (always do this, in order)

1. Read `docs/PROGRESS.md`. It says where we are and what to do next.
2. Read `docs/PLAN.md`. Find the current milestone and its "Done when" criteria.
3. Read `docs/DESIGN.md` if you are touching architecture, data models, or APIs.
4. Read `docs/DECISIONS.md` before proposing any new technology or changing an existing one.
5. Run `git log --oneline -15` and `git status` to confirm the repo matches PROGRESS.md.
   If they disagree, fix PROGRESS.md first and tell the user.
6. Run the existing tests (`make test`) so you know the starting state.

## Autonomy

- Briefly state the plan in the first message and proceed with implementation choices that follow DESIGN.md, PLAN.md, and DECISIONS.md.
- Debug errors, retry, and adapt. Record notable findings in PROGRESS.md.
- Stop and ask the user if you need a new dependency, want to change the stack, cannot meet a milestone's done criteria, would weaken isolation (including Docker socket access, host mounts, or sandbox networking), want to change the scope or order in PLAN.md, or need to spend money on real LLM calls.
- For milestone 1.5 (agent loop) and Phase 4 concurrency work, present the plan and wait for approval before implementing.
- Mark a milestone complete only after its required checks have actually run and passed. Skipped checks leave the milestone open.

## Work rules

- **One milestone at a time.** Work only on the current milestone in PLAN.md.
  Do not start the next one, and do not add features that are not in PLAN.md.
- **Simplest thing that works.** This is an MVP. Prefer boring, small, readable code.
  If you feel the urge to add a framework, queue, or abstraction not in DESIGN.md, stop and ask.
- **Respect the tech stack** in DESIGN.md. Changing it requires user approval and a new entry in DECISIONS.md.
- **Test as you go.** Every milestone must have at least one automated test or a runnable
  demo script that proves its "Done when" criteria.
- **Small commits.** Commit after each working sub-step with a clear message.
- Run CodeHarness development tests and lint in the local Python 3.11 `.venv`.
  For fixture verification, the host may also run temporary copies of our own
  committed demo repos and their reviewed reference fixes (D-16). User repos,
  agent-edited task code, and agent-generated task commands run only in sandboxes.
- **Never put API keys in code, logs, events, or sandboxes.** Use environment variables
  (see `.env.example`). Never commit `.env`.
- **Real LLM calls cost money or use limited quota.** Default to `MockLLM` for development and tests
  (`LLM_PROVIDER=mock`). Use a real provider only for the milestone demo that needs it, run it once,
  and never put real-LLM calls inside loops, retries, or automated test suites that run by default.
  Never print or log API keys. Provider details are in D-14 and DESIGN.md section 11a.

## Session end routine (always do this before stopping)

1. Make sure tests pass (or clearly note which fail and why).
2. Update `docs/PROGRESS.md`:
   - tick finished checkboxes in PLAN.md
   - update "Current state", "Next step", and "Known issues"
   - add a dated entry to the session log
3. Commit everything, including doc updates.
4. Tell the user in 3-5 lines: what was done, what works, what is next.

## Code conventions

- Python 3.11+, type hints everywhere, `ruff` for lint and format, `pytest` for tests.
- Async FastAPI. **Never call blocking code (Docker SDK, sync DB calls) directly inside
  `async def`.** Use `asyncio.to_thread` or an async library.
- Every log line and event carries the `task_id`.
- Task status changes go through one function (`transition_status`) that enforces
  the allowed transitions in DESIGN.md. Never set status ad hoc.
- Sandboxes are always destroyed in a `finally` block.
- Secrets and config come from environment variables via a single `config.py`.

## Definition of done (any milestone)

- The "Done when" criteria in PLAN.md are demonstrably met (command + expected result).
- Tests pass and `ruff` is clean.
- PROGRESS.md and PLAN.md are updated.
- Work is committed.

## Commands (keep this section current)

```
make setup     # install dependencies
make test      # run tests
make lint      # ruff check
make demo      # run the current phase's demo (see PROGRESS.md)
```
If a command does not exist yet, creating it is part of Milestone 1.0.
