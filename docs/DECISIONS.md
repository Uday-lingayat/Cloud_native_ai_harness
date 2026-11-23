# DECISIONS.md: Why we chose what we chose

Rule: before adding or changing a technology, check here. If you change something,
add a new entry (do not silently edit old ones). Mark old entries "Superseded by D-xx".

Format: Decision, Why, Alternatives not chosen, Revisit when.

---

### D-16 Host verification of committed demo fixtures
- **Decision:** Verify our own committed demo repos and reference fixes on temporary copies in the local Python 3.11 virtual environment. User repos and agent-edited task code run only in sandboxes.
- **Why:** Each fixture needs a reproducible failing baseline and a passing reference fix before it can be used in a sandbox or evaluation.
- **Alternative considered:** Requiring Docker for fixture verification would couple these data checks to the sandbox implementation.
- **Revisit when:** The source or trust assumptions for fixtures change.

### D-15 Local development checks on Windows
- **Decision:** Run CodeHarness tests and Ruff from a Python 3.11 virtual environment using GNU Make from PowerShell.
- **Why:** Sandbox integration tests starting in milestone 1.2 need to launch Docker containers from the host.
- **Alternative considered:** A development container would also need access to the host Docker daemon.
- **Revisit when:** The supported development environment changes.

### D-01 Docker containers as sandboxes
- **Why:** Works on any laptop and any Linux VM, fast to build, and the Docker SDK for Python is simple.
- **Not chosen:** Firecracker (stronger isolation, but needs KVM and is hard to develop with), Kubernetes (big setup, adds nothing to the demo), managed sandboxes like E2B (we would not be building the sandbox layer ourselves).
- **Mitigation:** `Sandbox` interface, so gVisor/Firecracker can be added later.
- **Revisit when:** we want stronger isolation or multi-machine scale.

### D-02 Agent loop written by hand, no LangChain/LangGraph
- **Why:** The loop is about 100 lines, easy to debug, and trivial to emit live events from. It is the core skill the project shows. Many real coding agents use custom loops.
- **Not chosen:** LangGraph (good for workflows, checkpointing; adds a learning curve and hides the loop).
- **Revisit when:** we want to show framework experience. Plan: reimplement `run_agent()` in LangGraph and compare in the README. Keep `run_agent(task, sandbox, llm, emit_event)` as a stable function signature.

### D-03 Agent loop runs in the backend, not inside the sandbox
- **Why:** The LLM API key never enters untrusted code, and defends against prompt injection leaking secrets. Easier budgets and event emission.
- **Tradeoff:** each tool call is a `docker exec` round trip.

### D-04 FastAPI (async) for the API
- **Why:** Standard for Python AI backends, native async and SSE support.
- **Not chosen:** Django (heavier, weaker async), Flask (sync-first), Node (splits languages for no gain).
- **Watch out:** never block the event loop with sync calls.

### D-05 SQLite first, Postgres optional later
- **Why:** Zero setup for Phases 1-3. Use SQLAlchemy so switching is a config change.
- **Not chosen now:** Postgres (fine, just extra setup), MongoDB (Postgres JSONB does the same).
- **Revisit when:** Phase 4 concurrency tests show write contention ("database is locked").

### D-06 No Redis or job queue in the MVP core
- **Why:** In-process asyncio background tasks with a concurrency cap are enough for the demo and much simpler.
- **Not chosen now:** Redis + RQ/arq/Celery, RabbitMQ, Kafka, Temporal.
- **Revisit when:** Phase 4.6, if time allows and we want separate worker processes.

### D-07 SSE for live streaming, not WebSockets
- **Why:** Data only flows server to browser; SSE is simpler and reconnects easily.
- **Reconnect rule:** load history from DB first, then stream, dedupe by per-task `seq`.
- **Revisit when:** we need browser-to-server interaction mid-run.

### D-08 React + Vite frontend
- **Why:** The resume says "React control plane". Vite is the simplest setup.
- **Not chosen:** Next.js (SSR not needed), Streamlit (poor for live multi-stream UI).

### D-09 MockLLM built in Phase 1
- **Why:** Deterministic tests and zero-cost load tests. Load tests must state that a mock LLM was used.

### D-10 Never reuse a container between tasks
- **Why:** Avoids state leakage and security issues. Warm pool = pre-started fresh containers, each used once.

### D-11 Cloud-native means containerized and deployed on a cloud VM
- **Why:** Same docker-compose setup on a rented Linux VM; benchmarks run there.
- **Resume honesty:** only keep numbers (100+ agents, under 5 s startup) that appear in `bench/results/`. If not measured, reword the resume.

### D-12 Network policy for sandboxes: (OPEN)
- **Question:** Network off by default; how do we allow `pip install`?
- **Options:** demo repos with dependencies baked into the image (simplest); a pip mirror; limited egress.
- **Default until decided:** network disabled, dependencies baked into the image.

### D-13 LangSmith for developer tracing and evals (optional, Phase 4 only)
- **Why:** Gives developer-side observability (per-run trace trees, token and cost numbers) and a way to evaluate agent quality on a set of tasks. It works with our hand-written loop and does not require LangChain, so it does not conflict with D-02.
- **Relationship to our events system:** our `events` table and SSE stream serve end users watching a task live. LangSmith serves the developer debugging and measuring runs. Neither replaces the other. Do not build the user-facing UI on top of LangSmith.
- **Rules:**
  - Optional and **off by default**. The project must run fully, and all tests must pass, without a LangSmith key.
  - Toggle via environment variables only; no tracing code path may change behavior when disabled.
  - Never trace load tests or benchmarks (volume, cost, and no insight).
  - Traces contain prompts and repo code and are sent to a third party. Use demo repos only, and state this in the README.
  - Verify the current LangSmith API and free-tier limits from the official docs before implementing; do not rely on memory.
- **Not chosen:** adopting LangChain/LangGraph just to get tracing (unneeded); other tools such as Langfuse or Arize Phoenix (valid alternatives; Langfuse is open source and self-hostable if we later want traces to stay local).
- **Milestones:** 4.5a (tracing), 4.5b (eval set). Do not start before Phase 3 is complete.
- **Revisit when:** privacy of traces becomes a concern (consider self-hosted Langfuse) or the free tier is insufficient.

### D-14 Provider-neutral, env-driven LLM client; free/cheap providers for development
- **Implementation (1.3, approved 2026-11-23):** Use the OpenAI Python SDK for the configurable Chat Completions endpoint. The adapter owns HTTP 429 backoff and disables SDK retries to keep the attempt count explicit.
- **Context:** The user has no free OpenAI/Anthropic credits. They have a Google AI Pro subscription, which does **not** include free Gemini API calls by itself, but provides monthly Google Cloud credits (about $10 at the time of writing, **verify current terms**) that can apply to the Gemini API once activated via the Google Developer Program "My Benefits" page and linked to a Cloud billing account. Consumer plan perks apply to the AI Studio web UI only; direct API use is billed separately.
- **Decision:** Implement one default `OpenAICompatibleLLM` driven by `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`. Most providers (Gemini via its OpenAI-compatible endpoint, Groq, OpenRouter, Ollama, OpenAI) accept this format, so switching provider is a config change. `MockLLM` remains the default for tests and load tests. `AnthropicLLM` / native `GeminiLLM` are optional extras only on request.
- **Cost plan:** develop and test with `MockLLM` (free); use real model calls only for milestone demos (1.5, Phase 2 exit, Phase 3 recording, evals). Set a budget alert (for example $5 and $10) in the provider console before the first real call. Candidate providers for free or cheap testing: Gemini (credits via the subscription benefit, or the limited free tier), Groq free tier, OpenRouter `:free` models (very low daily caps), Ollama locally (needs capable hardware). Limits change often; always check the live console.
- **Why not one provider SDK only:** locks us in, and free-tier limits shift without notice.
- **Why not third-party pooling gateways (for example `freellmpool`):** unvetted dependency that would receive our API keys; allowed only as an optional, user-approved experiment.
- **Risks:** free or small models are weaker at multi-step tool use and may fail tasks that a stronger model would solve. Provider tool-calling formats differ in small ways (normalize in one place). Free tiers may use prompts for training, so use demo repos only. Rate limits (requests and tokens per minute/day) can stop a run mid-way: backoff, then fail clearly.
- **Honesty rule:** the README and any eval results must state which model and provider produced them.
- **Revisit when:** the chosen provider's credits or limits change, or demo reliability is poor with the cheaper model.
