# DESIGN.md: Architecture (source of truth)

## 1. What we are building

A web platform where a user submits a coding task ("fix the failing test in this repo").
The system starts an isolated Docker sandbox, runs an AI agent loop that reads code,
edits files, and runs tests inside that sandbox, then returns a git patch.
The user watches the agent's reasoning, terminal output, and diff live in a React UI.
Many tasks can run in parallel.

Goal: a polished, honest, demo-able MVP with a GitHub README and demo video.
Non-goal: being production-grade or feature-complete.

## 2. Components

| Component | Tech | Responsibility |
|---|---|---|
| API server | FastAPI (async) | Create/list/get tasks, serve events, SSE stream |
| Database | SQLite for Phases 1-3 (via SQLAlchemy); Postgres allowed in Phase 4 | Tasks and events (source of truth) |
| Runner | Python asyncio background tasks inside the API process (Phase 2-3); separate worker processes + Redis queue (Phase 4, optional) | Owns one task's lifecycle |
| Sandbox | Docker via the Docker SDK for Python | Isolated environment where commands run |
| Agent loop | Plain Python + LLM provider SDK (tool calling). No LangChain. | Decide next action, call tools, stop |
| LLM client | Interface `LLM` with `MockLLM` and `OpenAICompatibleLLM` (env-driven: base URL, model, key); optional `AnthropicLLM`/`GeminiLLM` | Real model for demos and evals, scripted fake for tests/load. Provider is swappable via env vars only. |
| Frontend | React + Vite | Task list, new task form, live task detail view |

## 3. Key architecture rules

1. **The agent loop runs in the trusted backend, not inside the sandbox.**
   The sandbox only executes tool commands. The LLM API key never enters the sandbox.
2. **Sandbox is behind an interface** (`Sandbox` class: `start`, `exec`, `read_file`,
   `write_file`, `destroy`). Docker is the only implementation now; the interface allows
   swapping to gVisor or Firecracker later.
3. **LLM is behind an interface** with `MockLLM` and a provider-neutral `OpenAICompatibleLLM` (see D-14). `MockLLM` is built in Phase 1
   so tests and load tests never spend money.
4. **Every meaningful action emits an event** via one function, `emit_event(task_id, type, data)`.
   Events are stored in the DB and (when streaming exists) pushed to subscribers.
5. **Never reuse a container across tasks.** Warm pools hold fresh unused containers only.
6. **Success is judged by us, not the agent.** After the loop, the runner runs the test
   command itself; the task succeeds only if that passes.

## 4. Task lifecycle (state machine)

```
queued -> starting -> running -> succeeded
                         |-----> failed
any non-terminal state  -------> cancelled   (Phase 4, optional)
```
Allowed transitions live in one place (`transition_status`). Terminal states: succeeded, failed, cancelled.

Flow of one task:
1. API validates the request, inserts a task row (`queued`), starts the runner, returns `task_id`.
2. Runner sets `starting`, creates a sandbox from the prebuilt image, prepares the repo.
3. Runner sets `running` and executes the agent loop.
4. Runner runs the test command itself, runs `git diff`, stores the patch.
5. Runner sets the final status and destroys the sandbox in `finally`.

## 5. Agent loop (about 100 lines, in `agent/loop.py`)

```
messages = [system_prompt, task_prompt]
for step in range(MAX_STEPS):
    response = llm.complete(messages, tools)
    emit_event("reasoning", response.text)
    if no tool calls: break
    for call in response.tool_calls:
        emit_event("tool_call", ...)
        result = execute_tool(call, sandbox)     # truncated to a size limit
        emit_event("tool_result" / "terminal_output", ...)
        messages.append(result)
    stop if over step, token, or time budget
```

Tools: `list_dir`, `read_file`, `search` (grep), `write_file` or `str_replace`, `run_command`.
System prompt must say: do not delete or weaken tests to make them pass; stop when tests pass.
Tool outputs are truncated (for example 10k chars) to protect the context window.
Detect repeated identical actions and stop to avoid infinite loops.

## 6. Data model

**tasks**: `id`, `repo_url`, `prompt`, `test_command`, `status`, `created_at`, `started_at`,
`finished_at`, `patch` (text), `error` (text), `input_tokens`, `output_tokens`, `steps`.

**events**: `id`, `task_id`, `seq` (per-task counter, starts at 1), `type`, `data` (JSON), `created_at`.
Index on `(task_id, seq)`. Event types: `status_change`, `reasoning`, `tool_call`, `tool_result`,
`terminal_output`, `file_changed`, `error`, `done`.

## 7. API

| Method | Path | Purpose |
|---|---|---|
| POST | `/tasks` | Create a task, returns `{id, status}` |
| GET | `/tasks` | List tasks |
| GET | `/tasks/{id}` | Task details and final patch |
| GET | `/tasks/{id}/events?after_seq=N` | Event history |
| GET | `/tasks/{id}/stream` | SSE live events (Phase 3) |
| GET | `/health` | Health check |

SSE reconnect rule: the client loads history first, then opens the stream and ignores any
event with `seq` it already has. Set headers to disable proxy buffering.

## 8. Sandbox details

- Image: `codeharness-sandbox` (Python, git, pytest, common tools). Built from `sandbox/Dockerfile`.
- Limits per container: memory cap, CPU cap, PID limit, non-root user.
- Network: disabled by default. If a task needs `pip install`, use an allowed-mirror approach
  decided in DECISIONS.md. Do not silently enable full network.
- Per-command timeout and per-task timeout. Always destroy in `finally`.
- Containers carry a label (`codeharness=1`) so a cleanup script can remove orphans.
- Repo preparation: copy from a cached bare clone on the host, then `git checkout` a fresh branch.

## 9. Frontend (Phase 3)

Pages: task list with "New Task" form; task detail with three panes:
**Trace** (reasoning and tool calls), **Terminal** (command output), **Diff** (final or live patch).
Rules: batch event updates (flush every ~100 ms) to avoid freezing; render terminal output with an
ANSI-aware component; do not auto-scroll if the user scrolled up.
Use one SSE stream per open task detail page only (not one per card on the list page; the list polls).

## 10. Performance and scale (Phase 4)

- Prebuilt image and repo cache to get sandbox-ready time under 5 s.
- Optional warm pool of fresh idle containers.
- Concurrency cap (semaphore) with a configurable `MAX_CONCURRENT_TASKS`.
- Benchmarks (scripts in `bench/`): sandbox startup p50/p95; N concurrent tasks with `MockLLM`.
- Results go in the README with exact hardware and date. **Only claim numbers we measured.**

### Observability and evals (Phase 4, optional; see D-13)

- Two separate systems with different audiences: our own **events** (DB + SSE) are for end users
  watching a task live; **LangSmith** tracing is for the developer debugging and measuring runs.
- Tracing hooks live only at two points: the `LLM` client wrapper and the agent loop entry point.
  Nothing else in the codebase imports LangSmith. It is enabled only by env vars
  (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`) and is off by default.
- The system must behave identically with tracing off. Never enable it during benchmarks or load tests.
- **Eval set** (`evals/`): 10-20 small repos with planted bugs, and `evals/run_evals.py` which
  runs the agent on each and reports pass rate, steps, tokens, and time. Pass/fail is decided by
  our own test run. Results are saved to `evals/results/` and quoted in the README.

## 11. Folder structure

```
codeharness/
  AGENTS.md
  README.md
  Makefile
  docker-compose.yml
  .env.example
  docs/               DESIGN.md PLAN.md PROGRESS.md DECISIONS.md
  backend/
    app/
      main.py         FastAPI app
      config.py       env-based settings
      db.py models.py schemas.py
      api/            route modules
      runner/         task lifecycle, state machine
      agent/          loop.py tools.py prompts.py
      llm/            base.py mock.py openai_compatible.py factory.py (anthropic.py optional)
      sandbox/        base.py docker_sandbox.py
      events.py       emit_event
    tests/
  sandbox/Dockerfile
  demo_repos/         small repos with planted bugs
  frontend/           React + Vite app
  bench/              benchmark scripts
  evals/              eval set of buggy repos + run_evals.py (Phase 4, optional)
```

## 11a. LLM configuration (all via environment variables)

| Variable | Meaning |
|---|---|
| `LLM_PROVIDER` | `mock` (default for tests) \| `openai_compatible` \| `anthropic` |
| `LLM_BASE_URL` | Provider's OpenAI-compatible endpoint (for example Gemini, Groq, OpenRouter, Ollama at `http://localhost:11434/v1`) |
| `LLM_MODEL` | Exact model ID, copied from the provider's console/docs (IDs change often) |
| `LLM_API_KEY` | Secret; only in `.env`, never committed, never sent to a sandbox |
| `LLM_MAX_RETRIES`, `LLM_TIMEOUT_S` | Backoff and timeout settings |

Rules: switching provider must need no code change. Always log input/output token counts per call.
Handle 429s with exponential backoff and jitter; free tiers have tight request and token limits, so a
task must fail with a clear message (not hang) when limits are exhausted. Only the backend reads these
variables. Provider-specific cost control: set a budget alert in the provider console and a per-task
token budget in the agent loop.

## 12. Explicitly out of scope for the MVP

Auth and multi-user, billing, PR creation, multi-repo tasks, Kubernetes, Firecracker, Temporal,
LangChain/LangGraph (LangSmith tracing is allowed, optionally, in Phase 4 only), crash recovery, retries. Mention them in the README as future work only.
