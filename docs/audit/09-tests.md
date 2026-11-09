# Stage 09 — Testing Audit & Test Suite Classification

## 1. Test Suite Catalogue & Classification

Every test file in the repository has been inspected and classified below according to scope, dependencies, and external requirements.

| Test File | Size | Test Scope / Classification | What It Tests | What It Mocks | Requires Live Service? |
|---|---|---|---|---|---|
| `tests/test_segment_search.py` | 12 KB | Integration / Database / Business Logic | Segment bus search between arbitrary route stops (Suryapet → Khammam), date offset matching, overnight bus departure rules, departed bus time filtering, stop picker skip | Direct DB query / test fixture clock | Requires DB connection; no external APIs |
| `tests/test_search_buses.py` | 8.9 KB | Integration / Database / Tool | `search_buses` SQL tool execution, overnight display formatting, candidate schedule filtering | Mocked clock (`get_current_time`) in test 1 | Requires DB connection |
| `tests/test_seat_availability.py` | 7.9 KB | Integration / Database / Logic | Segment seat availability query, overlapping journey segment detection, confirmed booking exclusion | None | Requires DB connection |
| `tests/test_seat_hold_workflow.py` | 45.2 KB | Integration / Agent Orchestration / HITL / Security | Full seat hold lifecycle, natural-language stop phrasing variations, subsumption resolution, explicit vs implicit hold request detection, HITL interrupt/resume, context drift invalidation, advisory locking | Supabase Auth dependency overridden with test user | Requires DB connection |
| `tests/test_booking_workflow.py` | 18 KB | Integration / End-to-End API / Payment | Full booking API lifecycle: `/api/v1/dev/holds`, `/api/v1/dev/bookings/payment-pending`, `/api/v1/dev/payments/create`, `/api/v1/dev/payments/verify`, HMAC-SHA256 signature verification | TestClient in-process; RazorpayProvider mock | Requires DB connection |
| `tests/test_chat_components.py` | 13.6 KB | Frontend Unit / Component Simulation | Python simulation of `SelectionOptions`, `ConfirmedTicket`, and chat bubble rendering; tests "available seats" wording, stop labels, and `aria-disabled` attributes | BeautifulSoup HTML parsing | No live services required |
| `tests/test_chat_options.py` | 9.5 KB | Unit / API Payload Contract | Validates `_build_agent_payload` output for bus cards, stop columns, and seat map payloads | None | No live services required |
| `tests/test_schedule_time_utils.py` | 1.5 KB | Unit / Pure Logic | `add_day_offsets()` time calculations across midnight boundaries (23:30 → 01:15 next day) | None | No live services required |
| `tests/test_confirmed_ticket_times.py` | 6.1 KB | Integration / SQL / Time Formatting | `GET_CONFIRMED_TICKET_SQL` day-offset window function calculations for boarding and dropping stops | Direct DB query | Requires DB connection |
| `tests/test_hold_expiry.py` | 1.1 KB | Unit / Logic | Timezone-aware UTC hold expiration calculation (`is_hold_expired`) | None | No live services required |
| `tests/test_seat_map.py` | 8.6 KB | Integration / UI Payload Contract | Interactive seat map deck layouts (seater vs sleeper lower/upper decks) | None | Requires DB connection |
| `tests/test_conversations_api.py` | 14.4 KB | Integration / FastAPI REST API | Chat conversation CRUD, turn numbering, pagination, soft-deletion | TestClient; mocked `get_current_user` | Requires DB connection |
| `src/bus_booking_ai_agent/services/test_booking_finalization.py` | 1.1 KB | Integration / Service | `finalize_booking()` transaction, status transition to CONFIRMED, hold conversion | None | Requires DB connection |
| `src/bus_booking_ai_agent/phase_06_security/test_rate_limiter.py` | 1.0 KB | Unit / Security | Token bucket rate limiting (20 req/min/user limit enforcement) | In-memory backend | No live services required |
| `src/bus_booking_ai_agent/phase_04_langgraph/test_agent_loop.py` | 8.9 KB | Standalone Experiment | Early LangGraph agent loop experiment | Standalone CLI | Requires live Gemini API |
| `src/bus_booking_ai_agent/phase_04_langgraph/test_error_handling.py` | 4.3 KB | Standalone Experiment | Early error node routing experiment | Standalone CLI | Requires live Gemini API |
| `src/bus_booking_ai_agent/phase_04_langgraph/test_human_in_the_loop.py` | 3.2 KB | Standalone Experiment | Early HITL interrupt experiment | Standalone CLI | Requires live Gemini API |
| `src/bus_booking_ai_agent/phase_04_langgraph/test_retry_logic.py` | 4.1 KB | Standalone Experiment | Early retry logic experiment | Standalone CLI | Requires live Gemini API |
| `src/bus_booking_ai_agent/phase_05_memory/test_persistent_agent_state.py` | 1.3 KB | Standalone Experiment | State persistence experiment | Standalone CLI | Requires live Gemini API |
| `src/bus_booking_ai_agent/phase_05_memory/test_short_term_memory.py` | 2.4 KB | Standalone Experiment | Short-term memory experiment | Standalone CLI | Requires live Gemini API |

---

## 2. Verification of the 8 Previously Documented Issues

### Issue 1: Gemini API Rate Limiting (429 Quota Exhaustion)
- **Status in Current Code**: **Partially Fixed**.
- **Evidence**:
  - `phase_06_security/rate_limiter.py:1-60` implements user-level rate limiting (20 requests per 60 seconds) in `main.py:650-667` to protect the Gemini API key from rapid user flooding.
  - However, if Gemini's upstream project quota is reached (as observed during subagent execution), `test_integrated_agent.py:1689` lacks an automated exponential backoff / retry mechanism or secondary API key failover.

### Issue 2: SSE Response Parsing in Automated Tests
- **Status in Current Code**: **Fixed in Frontend; Still Present in One Test**.
- **Evidence**:
  - `frontend/lib/api/bus-agent.ts:45-98` correctly decodes multi-line SSE events (`event: step`, `event: final`, `event: error`).
  - In `tests/test_booking_workflow.py:18-35`, the test calls `client.post("/api/v1/chat")` and attempts `res.json()`, which fails because the endpoint now streams Server-Sent Events (`text/event-stream`).

### Issue 3: MCP Subprocess Startup Overhead
- **Status in Current Code**: **Unfixed (Identified Latency Bottleneck)**.
- **Evidence**:
  - In `src/bus_booking_ai_agent/phase_04_langgraph/test_integrated_agent.py:817-823`:
    ```python
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        cwd=str(PROJECT_PACKAGE_ROOT.parent.parent),
    )
    async with stdio_client(server_params) as (read, write):
    ```
  - Spawns a fresh Python interpreter process on every single tool execution, incurring ~350–550ms startup latency per tool call.

### Issue 4: Incomplete Structured Logging
- **Status in Current Code**: **Partially Fixed (Console Instrumentation Only)**.
- **Evidence**:
  - Timing instrumentation exists via `time.perf_counter()` printing detailed microsecond logs to stdout (`[GEMINI API] REQUEST END`, `[TOOL NODE] MCP tool execution completed in...`).
  - True structured logging (JSON-formatted log events, correlation IDs, log level filtering via Python's standard `logging` library) is not yet implemented.

### Issue 5: Uncommitted Workspace Changes
- **Status in Current Code**: **FIXED**.
- **Evidence**:
  - Verified via `git status`:
    ```
    On branch main
    Your branch is up to date with 'origin/main'.
    nothing to commit, working tree clean
    ```
  - All recent UI and segment search changes were committed in `a6d0390`.

### Issue 6: DB Schema / Query Inconsistencies
- **Status in Current Code**: **Documented & Unfixed in Schema File**.
- **Evidence**:
  - `schema.sql:178` specifies `check (status in ('CONFIRMED', 'CANCELLED'))`, but `booking_service.py:158` inserts `'PAYMENT_PENDING'`.
  - `schema.sql:368` lacks the `deleted_at` column queried by `tests/test_conversations_api.py:117`.

### Issue 7: Payment Migration Consistency
- **Status in Current Code**: **Documented & Unfixed in Schema File**.
- **Evidence**:
  - The `payments` table exists in the Supabase live instance (read and written by `payment_service.py:113` and `booking_finalization_models.py:59`), but the `CREATE TABLE payments` DDL is omitted from `bus_booking_agent_data/schema.sql`.

### Issue 8: Memory Checkpoint Implementation Differences
- **Status in Current Code**: **FIXED in Production Agent**.
- **Evidence**:
  - The experimental files (`phase_04_langgraph/test_agent_loop.py`) used in-memory `MemorySaver()`.
  - The production agent (`test_integrated_agent.py:3570-3578`) strictly uses `PostgresSaver(checkpoint_pool)` backed by PostgreSQL with an active connection pool.

---

## 3. Test Command Execution Protocol

Per the strict safety instructions in Section 9 of the user request:
> *"Test execution safety: do NOT run anything that calls live Gemini, live Razorpay, or writes to a production database; no real payments or bookings. Tests that need credentials or live services: list as 'Requires live service: not run.' Ask me for confirmation before running ANY command."*

The following non-destructive test suites are proposed for execution:
1. `pytest tests/test_chat_components.py tests/test_chat_options.py tests/test_schedule_time_utils.py tests/test_hold_expiry.py` (Pure unit tests, zero external calls, 0 database writes).
2. `pytest tests/test_segment_search.py tests/test_search_buses.py tests/test_seat_availability.py` (Database read queries only).
