# Stage 08 — Architectural Decisions Audit

This document audits the 19 core architectural decisions of the project against documented evidence in the repository, actual implementation code, and current operational validity.

---

## The 19 Architectural Decisions

### 1. Why Gemini?
- **Original Reason**: Documented in `README.md:134-148`. Chosen as Google's state-of-the-art model offering large context windows, fast multimodal/structured reasoning, low latency, and direct native Python SDK support.
- **Actual Implementation**: Configured in `src/bus_booking_ai_agent/config/gemini.py:12` with model `gemini-2.5-flash` (with earlier experiments on `gemini-3.5-flash`).
- **Evidence**: `README.md:142`, `config/gemini.py:12`.
- **Current Validity**: **Valid**. Fast execution (~1.2–2.0s per turn), cost-effective for high-frequency conversational routing, and provides structured function-calling.

---

### 2. Why `google-genai` Python SDK?
- **Original Reason**: Documented in `README.md:145-147`: "The project uses Google's Gemini Python SDK rather than an LLM abstraction layer for the initial learning stages so that the underlying concepts can be understood directly."
- **Actual Implementation**: Directly imported via `from google import genai` in `config/gemini.py:1`. The agent calls `client.interactions.create()` directly.
- **Evidence**: `README.md:145`, `config/gemini.py:1`.
- **Current Validity**: **Valid**. Eliminates fragile third-party wrapper churn; provides first-class support for Gemini's interaction continuation (`previous_interaction_id`).

---

### 3. Why LangGraph?
- **Original Reason**: Documented in `README.md:153-161`: "LangGraph will be introduced later for agent state, nodes, edges, conditional routing, loops, tool execution, checkpoints, and human interruption." Chosen because conversational booking is a stateful cyclical workflow requiring deterministic routing and pause/resume capabilities.
- **Actual Implementation**: `src/bus_booking_ai_agent/phase_04_langgraph/test_integrated_agent.py:3361-3578` (`StateGraph(AgentState)`).
- **Evidence**: `README.md:153`, `test_integrated_agent.py:15, 3361`.
- **Current Validity**: **Valid**. LangGraph's native `interrupt()` and `Command(resume=...)` support enables clean human-in-the-loop workflows without ad-hoc background polling or custom state machines.

---

### 4. Why LangChain for Prompt Templates?
- **Original Reason**: Curriculum design intended LangChain's `PromptTemplate` / `ChatPromptTemplate` for managing modular prompts.
- **Actual Implementation**: **Architectural divergence during development**. LangChain is **not** imported or used for prompt templates in production code. Production prompt construction is implemented in native Python (`build_llm_input` in `test_integrated_agent.py:887-955`). Only `langchain_core.runnables.RunnableConfig` is used.
- **Evidence**: `pyproject.toml:10-23` (no `langchain`), `test_integrated_agent.py:887`.
- **Current Validity**: **Acceptable divergence**. Native Python formatting avoids unnecessary dependency overhead, though formalizing prompt templates with Pydantic or LangChain would improve modularity if multi-prompt branching expands.

---

### 5. Why Model Context Protocol (MCP)?
- **Original Reason**: Documented in `README.md:166-170`: "MCP will eventually be used to expose bus, seat, and booking capabilities as tools that the agent can use." Standardizes tool exposure, decouples the tool runtime from the orchestrator, and enforces clean client-server boundaries.
- **Actual Implementation**: `phase_03_mcp/server/mcp_server.py` defines tools using `@server.list_tools()` and `@server.call_tool()`.
- **Evidence**: `README.md:166`, `phase_03_mcp/server/mcp_server.py:15`.
- **Current Validity**: **Valid architectural concept**, though subprocess startup overhead (see decision 6) impacts latency.

---

### 6. Why Custom MCP Client + Server?
- **Original Reason**: The project is a ground-up learning platform; building custom client/server handlers ensured complete visibility into JSON-RPC messaging over stdio, session handshakes, and tool schema discovery rather than using opaque black-box SDKs.
- **Actual Implementation**: `test_integrated_agent.py:801-842` (`call_mcp_tool()`) launches `mcp_server.py` as a Python subprocess using `stdio_client` and `ClientSession`.
- **Evidence**: `test_integrated_agent.py:817-830`.
- **Current Validity**: **Partially valid**. Excellent for educational transparency, but launching a subprocess on *every individual tool call* adds ~300-500ms of Python startup overhead. Needs evolution into a long-lived pooled server process.

---

### 7. Why PostgreSQL is Authoritative?
- **Original Reason**: Documented in `README.md:89-107`: "The LLM should not be responsible for inventing bus schedules, prices, seat availability, or booking information... Database -> Source of truth."
- **Actual Implementation**: All bus schedules, route stops, seat layouts, fares, holds, and bookings reside in Supabase PostgreSQL (`bus_booking_agent_data/schema.sql`).
- **Evidence**: `README.md:99`, `schema.sql:1-424`.
- **Current Validity**: **Essential & Non-negotiable**. Eliminates LLM hallucinations for operational travel data.

---

### 8. Why Memory is Separate from Application Data?
- **Original Reason**: User preferences (e.g. "I prefer window seats on the lower deck") are subjective, mutable, and advisory. Application data (real physical bus seats, schedule departure times, ticket fares) is objective and legally binding. Mixing them risks allowing user preferences to spoof real inventory.
- **Actual Implementation**: `user_memories` table stores preferences, injected as `<untrusted_memory>` in `test_integrated_agent.py:861`. Fares and bookings are stored in `fares` and `bookings`.
- **Evidence**: `test_integrated_agent.py:853` ("Memory is NOT authoritative application state").
- **Current Validity**: **Valid & Critical**. Prevents memory poisoning where a saved preference could override a database price or availability check.

---

### 9. Why Checkpointing is Separate from User Memory?
- **Original Reason**: Checkpointing represents the exact execution graph state of an active conversation thread (which node is running, pending interrupts, temporary tool arguments). User memory represents long-term cross-session knowledge about the human passenger.
- **Actual Implementation**: Checkpointing uses `PostgresSaver` in `checkpoints` tables (`test_integrated_agent.py:3570`). User memory uses `user_memories` (`memory_service.py:9`).
- **Evidence**: `test_integrated_agent.py:3570`, `memory_service.py:9`.
- **Current Validity**: **Valid**. Allows deleting or updating long-term memories without breaking active LangGraph thread checkpoints.

---

### 10. Why Physical Seats Have No Permanent Availability Column?
- **Original Reason**: Documented in `schema.sql:60-62`: "No `is_available` column: availability is derived per-schedule from `booking_seats`, not stored on the physical seat." A bus seat is physical hardware. Seat `1A` on Bus `AP01` is booked on Monday morning from Hyderabad to Suryapet, but free on Monday afternoon from Suryapet to Vijayawada, and completely free on Tuesday.
- **Actual Implementation**: `bus_seats` has only `is_active` (`schema.sql:56`). Availability is calculated dynamically by querying overlapping segments in `booking_seats` and `seat_holds`.
- **Evidence**: `schema.sql:60`, `check_seat_availability.py:51-118`.
- **Current Validity**: **Valid & Optimal relational design**. A boolean flag on `bus_seats` would corrupt multilegged and multi-date scheduling.

---

### 11. Why Fares Attach to Schedule Segments?
- **Original Reason**: Documented in `schema.sql:152-156`: Fares vary by exact boarding point, dropping point, travel date, day-of-week surge, and brand tier. Storing fare per `(schedule_id, boarding_stop_id, dropping_stop_id)` allows instant deterministic lookup without runtime calculation.
- **Actual Implementation**: Unique constraint on `fares (schedule_id, boarding_stop_id, dropping_stop_id)` (`schema.sql:147`).
- **Evidence**: `schema.sql:147`, `fares.csv`.
- **Current Validity**: **Valid**. Fast $O(1)$ indexed query; prevents dynamic price recalculation discrepancies.

---

### 12. Why Journey Overlap Matters?
- **Original Reason**: Long-distance buses make multiple stops. If passenger A travels Hyderabad → Suryapet (Seq 1→2), the bus seat becomes empty at Suryapet. Passenger B can safely book Suryapet → Vijayawada (Seq 2→4) on the exact same seat. Blocking the entire bus trip for a partial-distance passenger would cause catastrophic revenue loss.
- **Actual Implementation**: Overlap condition: `existing_boarding < requested_dropping AND existing_dropping > requested_boarding` in `check_seat_availability.py:76-79` and `hold_service.py:236-237`.
- **Evidence**: `check_seat_availability.py:76`, `hold_service.py:236`.
- **Current Validity**: **Valid & Industry Standard**. Reflects real-world intercity transit logistics.

---

### 13. Why Seat Selection Does Not Create a Hold?
- **Original Reason**: Browsing and tapping seats on a map is an exploratory user action. If every click created an active database lock, a curious user clicking 10 seats would lock the entire bus from other passengers.
- **Actual Implementation**: Clicking a seat only sets `booking_context["seat_number"]` in local/thread state (`test_integrated_agent.py:1955-1982`). It does **not** call `create_hold()`.
- **Evidence**: `test_integrated_agent.py:1967-1969` (system prompt rule 22).
- **Current Validity**: **Valid**. Prevents denial-of-service inventory locking.

---

### 14. Why Holds Need Explicit User Intent?
- **Original Reason**: System prompt rule 23 (`test_integrated_agent.py:126-129`): A temporary hold is a consequential action that locks a shared resource. The agent requires explicit conversational phrases ("hold my seat", "please reserve") before staging the action.
- **Actual Implementation**: `_is_explicit_hold_request()` checks regex `\b(hold|reserve|lock)\b` in `test_integrated_agent.py:1445-1456`.
- **Evidence**: `test_integrated_agent.py:1445, 1955`.
- **Current Validity**: **Valid**. Ensures user intentionality before triggering human approval cards.

---

### 15. Why Human Approval (HITL)?
- **Original Reason**: Autonomous agents must not commit irreversible or consequential state changes (locking inventory, generating payable orders) without explicit human confirmation.
- **Actual Implementation**: LangGraph `interrupt()` in `approval_node()` (`test_integrated_agent.py:2811`) pauses the graph and surfaces `ApprovalCard` to the user.
- **Evidence**: `test_integrated_agent.py:2739-2840`.
- **Current Validity**: **Valid**. Fundamental safety guardrail for commercial transactional agents.

---

### 16. Why Booking and Payment are Separate?
- **Original Reason**: A booking must exist in `PAYMENT_PENDING` status before generating a payment gateway order (Razorpay requires an internal receipt/reference and exact amount). Merging them into a single step would risk collecting money for a booking that failed to insert into the database.
- **Actual Implementation**: `create_payment_pending_booking()` runs first, generating `booking_reference`. Then `prepare_payment()` calls Razorpay `create_order()` with the booking amount and ID.
- **Evidence**: `test_integrated_agent.py:3182-3238`, `payment_service.py:215-285`.
- **Current Validity**: **Valid & Standard payment architecture**.

---

### 17. Why Payment is Verified on the Backend?
- **Original Reason**: The frontend client runs in an untrusted browser environment. A malicious user could forge a JavaScript callback saying "payment succeeded". Only the backend, possessing the Razorpay Key Secret, can cryptographically verify the HMAC-SHA256 signature.
- **Actual Implementation**: `POST /api/v1/payment/verify` receives `razorpay_signature` and verifies it via `RazorpayProvider.verify_payment_signature()` using `hmac.new()` before updating `payments` to `SUCCESS`.
- **Evidence**: `payment_service.py:326-340`, `main.py:484-565`.
- **Current Validity**: **Valid & Mandatory for PCI/financial security**.

---

### 18. Why Concurrency Locking?
- **Original Reason**: Between the moment seat availability is read and the moment a hold is inserted, another user could submit a hold for the exact same seat.
- **Actual Implementation**: `pg_advisory_xact_lock(hashtextextended(schedule_id || ':' || seat_id, 0))` in `hold_service.py:326` serializes conflicting requests.
- **Evidence**: `hold_service.py:326`.
- **Current Validity**: **Valid**. Bulletproof double-booking prevention at the database engine level.

---

### 19. Why User-Specific Thread IDs?
- **Original Reason**: In multi-user web applications, conversation threads must be isolated. If thread IDs were plain integers or sequential IDs, User A could inspect or resume User B's booking session.
- **Actual Implementation**: LangGraph thread ID is constructed as `f"{current_user.id}:{conversation_id}"` (`main.py:694, 733`). Both `run_agent` and `approve_agent_action` verify that the thread user matches the JWT authenticated user.
- **Evidence**: `main.py:694`, `test_integrated_agent.py:3685-3689`.
- **Current Validity**: **Valid & Secure**. Guarantees tenant isolation across all checkpointer reads and resumes.
