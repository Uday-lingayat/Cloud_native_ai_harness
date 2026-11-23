# PLAN.md: Phases and milestones

Rules: work top to bottom. Tick a box only when its "Done when" is demonstrably true.
Do not start a phase until the previous phase's exit check passes.

---

## Phase 1: Agent fixes a bug from the command line (the core)

**Goal:** `make demo` runs one agent that fixes a planted bug in a demo repo, inside a Docker sandbox.

- [x] **1.0 Project skeleton**
  Repo layout from DESIGN.md, `pyproject.toml`, Makefile (`setup`, `test`, `lint`, `demo`), `.env.example`, ruff + pytest configured.
  *Done when:* `make setup && make test && make lint` run (even with one trivial test).

- [x] **1.1 Demo repos**
  Create `demo_repos/buggy_calc/` (small Python project, one failing pytest test, an obvious fix) and a second slightly harder one.
  *Done when:* `pytest` in each demo repo fails as designed, and the fix is a few lines.

- [x] **1.2 Sandbox image + `Sandbox` class**
  `sandbox/Dockerfile`; `Sandbox` interface and `DockerSandbox` with `start`, `exec(cmd, timeout)`, `read_file`, `write_file`, `destroy`; memory/CPU/PID limits, non-root, label.
  *Done when:* a test starts a sandbox, copies a demo repo in, runs `pytest`, sees the failure output, and destroys the container (verified: no container left).
  - Run commands with in-container GNU `timeout` targeting the process group. The sandbox survives an ordinary timeout. Force-remove it only if the host-side backstop deadline expires.
  - Probe `put_archive` with a read-only root filesystem and writable workspace first. If the probe shows incompatibility, use a writable root filesystem and record the result and fallback as D-17. Drop all capabilities, enable no-new-privileges, run as non-root, disable networking, and set memory, CPU, and PID limits. Never mount host folders or the Docker socket.
  - Keep the first 2 KiB and last 8 KiB of combined command output with a truncation marker between them to preserve the pytest summary.
  - Use `init=True` and build with `make sandbox-image`. Orphan cleanup filters by label and minimum age, skips active container IDs, and supports dry-run mode.
  - Require the Docker integration tests and `scripts/verify_demo_repos.py --docker` to run and pass against a live Docker engine. Skips leave this milestone open.

- [x] **1.3 LLM interface + MockLLM**
  `LLM` base class; `MockLLM` (plays back a scripted list of tool calls); `OpenAICompatibleLLM` (default real provider; takes `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` from env, so it works with Gemini's OpenAI-compatible endpoint, Groq, OpenRouter, Ollama, and OpenAI with no code change). `AnthropicLLM` and a native `GeminiLLM` are optional extras, added only if the user asks. A factory `get_llm()` picks the implementation from `LLM_PROVIDER` (`mock` | `openai_compatible` | `anthropic`). See D-14.
  Verify the current provider docs (endpoint URLs, model IDs, tool-calling format) before coding; do not rely on memory. Normalize tool-call responses into one internal format, because providers differ in small ways. Handle 429 rate-limit errors with exponential backoff and a clear error message. Add a pricing/usage note: log input/output token counts per call.
  *Done when:* unit tests pass using MockLLM; the real provider has a smoke test (one tool-calling round trip) that is skipped when no API key is set; switching provider requires only env var changes.

- [x] **1.4 Tools**
  `list_dir`, `read_file`, `search`, `write_file`/`str_replace`, `run_command`, with output truncation and path safety (stay inside the workspace).
  *Done when:* each tool has a test running against a real sandbox.

- [ ] **1.5 Agent loop**
  The scripted Docker demo and independent verification pass. The real-provider demo and Phase 1 exit check are pending.
  `agent/loop.py` as in DESIGN.md: step, token, and time budgets; repeated-action detection; emits events through a simple in-memory `emit_event` (printing to console for now).
  *Done when:* with MockLLM, the loop completes a scripted fix; with a real provider (set in `.env`), `make demo` fixes `buggy_calc` and prints the final `git diff`.

**Phase 1 exit check:** record the exact command and its output in PROGRESS.md. A real model fixes the bug end to end, and our own test run (not the agent's claim) confirms it.

---

## Phase 2: Backend server and database

**Goal:** start a task with an HTTP request, read the result later.

- [ ] **2.1 DB models + migrations/setup**: `tasks` and `events` tables (SQLite). *Done when:* tests create and read rows.
- [ ] **2.2 State machine**: `transition_status` with allowed transitions. *Done when:* invalid transitions raise; tests cover all of them.
- [ ] **2.3 `emit_event`**: writes to DB with per-task `seq`. *Done when:* events come back ordered with no gaps.
- [ ] **2.4 Runner**: full lifecycle (starting, repo prep, agent loop, our own test run, git diff, final status, destroy in `finally`). *Done when:* a runner test with MockLLM goes from `queued` to `succeeded` with a stored patch, and the sandbox is gone even when the agent errors.
- [ ] **2.5 FastAPI endpoints**: `POST /tasks`, `GET /tasks`, `GET /tasks/{id}`, `GET /tasks/{id}/events`, `/health`; runner started as an asyncio background task. *Done when:* `curl -X POST /tasks` followed by polling `GET /tasks/{id}` shows `succeeded` and a patch.
- [ ] **2.6 `docker-compose.yml`** for the backend. *Done when:* `docker compose up` brings the API up and the curl flow works.

**Phase 2 exit check:** curl flow works with a real provider on a demo repo; documented in PROGRESS.md.

---

## Phase 3: Live view

**Goal:** watch an agent work in the browser.

- [ ] **3.1 SSE endpoint** `/tasks/{id}/stream` (history then live, dedupe by `seq`, no-buffer headers). *Done when:* `curl -N` shows events arriving live.
- [ ] **3.2 Frontend scaffold**: React + Vite, API client, task list page with polling, new task form.
- [ ] **3.3 Task detail page**: Trace pane, Terminal pane (ANSI-aware), Diff pane; batched rendering; reconnect-safe.
  *Done when:* submitting a task in the UI shows the trace updating live and the final diff.
- [ ] **3.4 Frontend in docker-compose**. *Done when:* one `docker compose up` serves UI + API.

**Phase 3 exit check:** screen-record a full run (submit, live trace, tests fail then pass, patch shown).

---

## Phase 4: Parallelism, speed, cloud, polish

**Goal:** back the resume claims with measured numbers and ship it.

- [ ] **4.1 Concurrency control**: `MAX_CONCURRENT_TASKS` semaphore; queue excess tasks as `queued`. *Done when:* a test launches N tasks and only the cap run at once.
- [ ] **4.2 Prebuilt image + repo cache**: cached bare clone, `git fetch` then checkout. *Done when:* startup time measured before and after.
- [ ] **4.3 Warm pool (optional)**: fresh idle containers, each used once, refilled in the background.
- [ ] **4.4 Benchmark scripts** in `bench/`: sandbox-ready time (p50/p95 over many runs); N concurrent tasks with MockLLM (N = 10, 50, 100). Save raw results as files in `bench/results/`.
- [ ] **4.5 Orphan cleanup script** (remove labeled containers older than X).
- [ ] **4.5a (Optional) LangSmith tracing**: wrap the LLM client and the agent loop with LangSmith tracing (`@traceable` and the wrapped provider client). Controlled by env vars (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`); **off by default**. Check the current LangSmith docs for the exact API before coding. Never enable it for load tests or benchmarks. See D-13.
  *Done when:* with tracing on, one real demo run appears in LangSmith as a tree (LLM calls, tool calls, token counts); with tracing off or no key, the whole project runs and all tests pass unchanged.

- [ ] **4.5b (Optional) Eval set**: 10-20 small demo repos with planted bugs in `evals/` (reuse `demo_repos/` where possible), plus `evals/run_evals.py` that runs the agent on each one and reports pass rate, average steps, tokens, and time. Pass/fail is decided by our own test run, never the agent's claim. Results saved to `evals/results/` as JSON and summarized in the README. LangSmith dataset/experiment upload is optional on top.
  *Done when:* one command runs the full eval set with a real provider and prints a results table; a MockLLM variant runs in tests to verify the eval script itself.

- [ ] **4.6 (Optional) Redis + separate worker processes**: only if time allows; record the decision in DECISIONS.md first.
- [ ] **4.7 Cloud deployment**: run the same compose setup on one Linux VM; run benchmarks there; note VM specs.
- [ ] **4.8 README**: what it is, architecture diagram, quick start, GIF, benchmark table (with hardware and "MockLLM used" noted), eval results if 4.5b was done (model used, pass rate, date), a note that LangSmith tracing (if enabled) sends prompts and repo code to a third party, limitations and future work.
- [ ] **4.9 Demo video** (2-4 min): submit task, live trace, tests fail then pass, patch, then many parallel agents.
- [ ] **4.10 Resume check**: compare resume bullets against measured results. Adjust wording to match reality.

**Phase 4 exit check:** a stranger can clone the repo, follow the README, and reproduce the demo.
