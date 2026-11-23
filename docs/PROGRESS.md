# PROGRESS.md: Living status (update at the end of EVERY session)

## Current state

- **Current phase:** Phase 1
- **Last completed milestone:** 1.0 Project skeleton
- **Current milestone:** 1.1 Demo repos (pending)
- **Last updated:** 2026-11-23
- **Does `make test` pass?** Yes, one backend package-import test passed.

## What works right now

`make setup` installs the backend package, pytest, and Ruff in the project's Python 3.11 virtual environment. The example environment lists all six LLM settings and defaults to `mock`.

## Next step

Milestone 1.1 will add two demo repositories with planted bugs.

## Known issues / open questions

- None yet.

## How to run the current demo

Use native Windows PowerShell with GNU Make. On a machine with Chocolatey, install Make once from an elevated PowerShell with `choco install make -y`, then reopen PowerShell and check `make --version`.

From the repository root, run each command on its own line:

```powershell
make setup
make test
make lint
make demo
```

Expect setup to install the development dependencies, pytest to report `1 passed`, and Ruff to report clean lint and formatting. The demo target prints `Project skeleton ready. The runnable agent demo arrives in milestone 1.5.`

## Environment notes

- LLM provider: set via `.env` (`LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`; see `.env.example` and D-14).
  The user plans to use Gemini via Google AI Pro developer credits (needs activation and a Cloud billing account) and `MockLLM` for most development.
- Before the first real LLM call: confirm the user has set a provider budget alert.
- Local checks use Python 3.11 in `.venv`. Make invokes its interpreter directly, so activation is optional. On Windows, setup selects `py -3.11`, then tries uv if the launcher is absent, then falls back to `python` on PATH. This machine used its installed uv-managed Python 3.11.12 and GNU Make 4.4.1.
- Docker is required starting with the sandbox integration tests in 1.2. Run benchmarks on a Linux cloud VM.

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

### 2026-11-23
- Did: Created the package and directory skeleton, local Make targets, pytest and Ruff configuration, and example environment. Verified Git ignores local secrets, the virtual environment, and tool caches.
- Milestones completed: 1.0.
- Tests: `make setup` succeeded, `make test` reported one pass, and `make lint` passed both Ruff checks. Verified the `make demo` status message.
- Decisions made: Use native PowerShell and a Python 3.11 virtual environment for development checks (D-15).
- Left off at: The project skeleton is ready. The demo repository directory contains only its Git placeholder.
- Next: Milestone 1.1, demo repositories.

---

## Note on optional work

Milestones marked "(Optional)" in PLAN.md (4.3, 4.5a, 4.5b, 4.6) are done only after all
non-optional Phase 4 milestones, and only if the user confirms. Do not start them earlier.
