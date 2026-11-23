# PROGRESS.md: Living status (update at the end of EVERY session)

## Current state

- **Current phase:** Phase 1
- **Last completed milestone:** 1.3 LLM interface and MockLLM
- **Current milestone:** 1.4 Sandbox tools (pending)
- **Last updated:** 2026-11-23
- **Does `make test` pass?** Yes. Eleven tests passed, including eight offline LLM tests and two live Docker tests, with zero skips.

## What works right now

`make setup` installs the backend package, pytest, and Ruff in the project's Python 3.11 virtual environment. The example environment lists all six LLM settings and defaults to `mock`.

The calculator and date-range demo repos each have a task README, a machine-readable manifest, and an independently runnable pytest suite. Their reference patches live in `scripts/reference_fixes/`.

`DockerSandbox` runs commands and handles UTF-8 workspace files in a fresh offline container. Copy a repo before running commands or using the file helpers. Each container gets an anonymous writable workspace volume, removed during destruction. The orphan cleanup helper defaults to dry-run and accepts a minimum age and the full IDs of active tasks.

## Next step

Milestone 1.4 will add and test the tools that operate on a sandbox workspace.

## Known issues / open questions

- None yet.

## How to run the current demo

Use native Windows PowerShell with GNU Make. On a machine with Chocolatey, install Make once from an elevated PowerShell with `choco install make -y`, then reopen PowerShell and check `make --version`.

From the repository root, run each command on its own line:

```powershell
make setup
docker version
make sandbox-image
make test
make lint
.\.venv\Scripts\python.exe scripts\verify_demo_repos.py
.\.venv\Scripts\python.exe scripts\verify_demo_repos.py --docker
make demo
```

Use the Linux engine in Docker Desktop and confirm `docker version` prints a Server section. Building the image needs package downloads on a cold cache. Expect the backend suite to report `11 passed` and Ruff to report clean lint and formatting. Both verifier modes extract the committed fixtures from Git HEAD. Docker mode runs each baseline and each fixed copy in a fresh offline container. Both print:

```text
buggy_calc: 3 passed, 1 failed
buggy_calc: 4 passed, 0 failed
date_ranges: 4 passed, 1 failed
date_ranges: 5 passed, 0 failed
```

`make demo` points to the fixtures. The runnable agent demo arrives in milestone 1.5.

### LLM configuration and smoke check

`app.llm.factory.get_llm()` defaults to a fresh mock. Supply a sequence of `Reply` objects with `script=` for deterministic tool calls. For a compatible service, set `LLM_PROVIDER=openai_compatible`, its base URL, its tool-capable model ID, and its key in the root `.env`. Process environment variables take precedence. For a local Ollama endpoint that ignores authentication, use a non-secret placeholder key. Use `close()` when finished with the client.

The adapter logs task ID, provider, model, and reported input/output tokens at INFO level. Missing usage is recorded as unknown. To estimate cost, apply the provider's current rates for the selected model. Mock replies default to zero tokens. HTTP 429 responses use the configured retry limit with exponential backoff and jitter.

The live smoke check makes one request with retries disabled. After confirming the provider budget alert and authorizing quota use, run from PowerShell:

```powershell
$env:RUN_LIVE_LLM = '1'
try { .\.venv\Scripts\python.exe -m pytest -q -rs backend/smoke/test_llm_provider.py }
finally { Remove-Item Env:RUN_LIVE_LLM }
```

The smoke check skips when the key or explicit opt-in is absent. The default suite exercises the real SDK against intercepted HTTP responses. Gemini endpoint and function schema reference: [Google's OpenAI compatibility guide](https://ai.google.dev/gemini-api/docs/openai#function-calling).

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
- Did: Implemented the common LLM interface, scripted mock, environment-based factory, and OpenAI-compatible client. Added token accounting, bounded rate-limit retries, and a single-request provider smoke test.
- Milestones completed: 1.3.
- Tests: `make setup`, `make test` (11 passed), and `make lint` passed. Separately checked the no-key and opt-in guards and the smoke assertion with an intercepted tool-call response. No live provider request or quota use.
- Decisions made: Approved the OpenAI Python SDK for D-14's compatible adapter.
- Next: Milestone 1.4.

### 2026-11-23
- Did: Implemented the Docker sandbox image, lifecycle, workspace file and archive operations, command deadlines, head/tail output cap, orphan cleanup helper, and Docker verifier mode.
- Milestones completed: 1.2.
- Tests: Docker Desktop Engine 28.5.2 (linux/amd64), `make sandbox-image` succeeded, `make test` returned three passes with zero skips, and `make lint` passed. Both verifier modes produced the four expected results above. A final `docker ps -a --filter label=codeharness=1 -q` returned no IDs.
- Findings: The SDK uploaded a tar into an anonymous volume on a read-only root filesystem. UID 10001 could modify the uploaded file. The conditional D-17 fallback was unnecessary. Windows setup now reuses the virtual environment after an attempted recreation hit a locked interpreter.
- Left off at: The sandbox survived the process-group timeout test and the integration test confirmed removal of its container and anonymous volume.
- Next: Milestone 1.3.

### 2026-11-23
- Did: Added the calculator and date-range demos, README prompts, manifests with pytest node IDs, external reference patches, and a local verifier.
- Milestones completed: 1.1.
- Tests: The verifier confirmed each declared failure and all nine tests passed after the respective one-line fixes. The backend test and both Ruff checks passed.
- Decisions made: D-16 permits host verification on temporary copies of our committed fixtures and reference fixes. User repos and agent-edited task code run only in sandboxes.
- Left off at: Both fixtures are ready for sandbox testing.
- Next: Milestone 1.2.

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
