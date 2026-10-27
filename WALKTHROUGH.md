# Walkthrough: Segment-Aware Bus Search & UI Refinements

## 1. Overview & Objectives

This implementation delivers segment-aware bus search across intermediate route stops (e.g., searching Suryapet to Khammam on a Hyderabad → Vijayawada route), accompanied by user-interface and system prompt wording refinements.

All hard constraints were strictly honored:
- **No changes to restricted files**: `booking_service.py`, `hold_service.py`, `payment_service.py`, and `schema.sql` remain completely unmodified (`git diff` is empty).
- **ID privacy**: No internal database UUIDs are leaked to user-facing payloads in bus/stop options.
- **Determinism**: Calculations (fares, day offsets, seat availability, departure/arrival display times) are computed deterministically in tools/backend rather than fuzzy LLM guessing.
- **Dependency discipline**: Verified that no toast library existed in `frontend/package.json`; implemented an accessible, responsive status banner rather than adding an external dependency.

---

## 2. Investigation Findings

### (a) Search Matching: Origin/Destination vs. Stop Names
- **Previous behavior**: `SEARCH_BUSES_SQL` in `search_buses.py` strictly enforced `WHERE r.origin = :origin AND r.destination = :destination` alongside exact equality on `origin_stop.stop_name = :origin` and `destination_stop.stop_name = :destination`.
- **Limitation**: Any attempt to search between intermediate stops (e.g. Suryapet to Khammam) returned empty results because routes are defined between terminal cities (e.g. Hyderabad to Vijayawada).
- **Resolution**: Refactored the SQL query to join `route_stops` case-insensitively on `origin_stop.stop_name ILIKE :origin` and `destination_stop.stop_name ILIKE :destination` constrained by `origin_stop.sequence_number < destination_stop.sequence_number`, `origin_stop.is_boarding_allowed = TRUE`, and `destination_stop.is_dropping_allowed = TRUE`. Terminal routes follow the exact same path.

### (b) Departed Bus Handling
- **Previous behavior**: `search_buses.py` did not check whether the boarding departure time had already elapsed on today's travel date. Departed buses on the current calendar day were returned.
- **Resolution**: Added IST (+05:30) timestamp validation. Boarding departure datetime is constructed by combining `schedule.travel_date + boarding_departure_day_offset` with `departure_time` in IST. Any bus with `boarding_departure_datetime <= now_ist` is excluded.

### (c) Pre-existing Assumptions on Stop Selection
- **Previous behavior**: In `test_integrated_agent.py`, `_resolve_selected_bus()` unconditionally purged `boarding_stop_id`, `dropping_stop_id`, `boarding_stops`, and `dropping_stops` upon bus selection. When `ensure_selected_schedule_details()` called `get_bus_details()`, `update_booking_context_from_tool_result()` saw empty stop IDs and set `options_kind = "stops"`.
- **Resolution**: In `_resolve_selected_bus()`, when a candidate represents a segment search (`is_segment_search = True`), `boarding_stop_id`, `dropping_stop_id`, `boarding_stop_name`, `dropping_stop_name`, and segment `fare` are auto-populated in `booking_context`. The stop options (`options_kind = "stops"`) are bypassed, allowing the agent to proceed directly to segment seat availability and display the interactive seat map. For full-route searches without pre-chosen stops, the stop picker continues to be presented.

### (d) Toast Library Verification in Frontend
- **Verification**: Examined `frontend/package.json` and `frontend/components/ui/`. No toast library (such as `sonner` or `react-hot-toast`) or custom toast component existed.
- **Decision**: In compliance with instructions, no new package was installed. Instead, an accessible status banner (`role="status"`, `aria-live="polite"`) with dismiss action was built into `SelectionOptions`.

---

## 3. UI & Wording Refinements (Part A)

1. **Available Seats Label**:
   - Renamed user-facing bus card detail from `"X seats free"` to `"X available seats"`.
   - Internal tool dictionary sets `free_seat_count` as primary and `free_seats` as a backward-compatibility alias. The field is never named `available_seats` (which is reserved for the list of available seat objects in booking context).
2. **Stop Picker Card Streamlining**:
   - Removed `"Stop N · "` prefix from user-facing stop buttons in `selection-options.tsx`. Buttons display only the stop name and formatted time (e.g. `10:15 PM` or `1:00 AM (next day)`).
   - Preserved `sequence_number` in payload and component state for validation and sequence disabling logic.
3. **Accessible Invalid Stop Pair Feedback**:
   - Replaced `disabled={pairIsInvalid}` with `aria-disabled={pairIsInvalid}` so click events fire.
   - When an invalid stop is clicked:
     - The selection is not applied.
     - An accessible feedback message is displayed (e.g. `"Choose a dropping stop after Suryapet"` or `"Choose a boarding stop before Khammam"`).
     - No chat message is dispatched.
   - When a valid stop pair is chosen, the "Continue" button is enabled.
4. **System Prompt Rules**:
   - **Rule 33 & 34**: Updated to refer to `available seats` / `free_seat_count`.
   - **Rule 18**: Clarified that when stops are already pre-selected from a segment search, the agent must proceed directly to `check_seat_availability`.
   - **Rule 39**: Dictates that when the seat map is rendered, the agent outputs a single short directive sentence (e.g. `"Pick a seat on the map below to continue."`) and never mentions or recommends individual seat numbers in text.
   - **Rule 40**: Instructs the model that it can search between any two route stops by passing their names to `search_buses`.

---

## 4. Segment-Aware Bus Search Implementation (Part B)

### `search_buses.py`
- **Stop Pair Query**: Queries any route containing the requested boarding and dropping stops where `boarding.sequence_number < dropping.sequence_number`, `origin_stop.stop_name ILIKE :origin`, and `destination_stop.stop_name ILIKE :destination`.
- **Date Matching Rule**:
  - PostgreSQL pre-filters: `s.travel_date >= (CAST(:travel_date AS DATE) - 2) AND s.travel_date <= CAST(:travel_date AS DATE)`.
  - Python matches: `boarding_date = schedule_travel_date + timedelta(days=boarding_departure_day_offset)`. If `boarding_date != request.travel_date`, the schedule is skipped.
- **Departed Bus Filtering Rule**:
  - `boarding_departure_datetime = datetime.combine(boarding_date, dep_time, tzinfo=IST)`.
  - If `boarding_departure_datetime <= now_ist`, the bus is excluded.
  - Accepts an optional `now` parameter and exposes `get_current_time()` for deterministic testability.
- **Segment Output Data**:
  - `boarding_stop`: `{"id": UUID, "name": str, "departure_display": str}`
  - `dropping_stop`: `{"id": UUID, "name": str, "arrival_display": str}`
  - `fare`: Segment fare from `fares` table.
  - `free_seat_count` / `free_seats`: Live count accounting for confirmed bookings and active unexpired seat holds across overlapping segments.
  - `is_segment_search`: `True` when search stops differ from terminal route endpoints.

### Context Auto-population & Skip Picker
- In `_resolve_selected_bus()`, when `selected["is_segment_search"]` is true, the resolved booking context receives `boarding_stop_id`, `dropping_stop_id`, `boarding_stop_name`, `dropping_stop_name`, and segment `fare`.
- `options_kind` is cleared and not re-armed with `"stops"`, allowing immediate invocation of `check_seat_availability`.

---

## 5. Read-Only Report: Payment Finalization on Expired Seat Hold

### Code Inspection
- **Source**: `src/bus_booking_ai_agent/services/booking_finalization_models.py` (lines 321–342) and `src/bus_booking_ai_agent/services/payment_service.py` (lines 352–473).

### What Happens When `expires_at` Has Passed
1. In `payment_service.py` (`verify_payment`), Razorpay signature verification succeeds and the payment record in the database is marked as `SUCCESS`.
2. Next, `finalize_booking` is invoked within a dedicated database transaction.
3. Steps in `finalize_booking`:
   - Step 6 loads the active hold via `GET_ACTIVE_HOLD_SQL` (which matches `status = 'ACTIVE'`).
   - Step 7 checks `hold["status"] == "ACTIVE"`.
   - Step 8 executes:
     ```sql
     SELECT CURRENT_TIMESTAMP < :expires_at AS is_valid;
     ```
   - If `is_valid` is false, it raises:
     ```python
     raise FinalizationHoldExpiredError("The seat hold has expired.")
     ```
   - The transaction is aborted and rolled back.
   - The booking remains in `PAYMENT_PENDING` status; it is **never** confirmed (`CONFIRMED`).

### Can Another User Take the Seat During That Window?
- **Yes**: In `hold_service.py` (`_has_active_hold_conflict`) and in the availability SQL queries (`search_buses.py` and `check_seat_availability.py`), an active hold is filtered by:
  ```sql
  sh.status = 'ACTIVE' AND sh.expires_at > CURRENT_TIMESTAMP
  ```
- As soon as `CURRENT_TIMESTAMP >= expires_at`, the expired hold is no longer considered a conflicting hold.
- Consequently, another user (User B) checking seat availability or requesting a seat hold can immediately acquire an active hold on that exact seat.
- If User A completes payment after their hold expired, User A's payment has succeeded at the gateway, but `finalize_booking` will reject the confirmation with `FinalizationHoldExpiredError`. User A does not receive the ticket, and the booking system requires a reconciliation / refund workflow.

---

## 6. Verification & Test Outcomes

### Unit & Integration Tests Run
1. `tests/test_segment_search.py` (6 tests - all passing):
   - `test_segment_search_suryapet_to_khammam_same_day`
   - `test_overnight_bus_reaching_boarding_stop_next_day`
   - `test_departed_bus_filtering`
   - `test_stops_in_wrong_order_returns_empty`
   - `test_bus_selected_from_segment_results_skips_stop_picker`
   - `test_bus_options_user_facing_wording_available_seats`
2. `tests/test_search_buses.py` (2 tests - all passing):
   - `test_search_buses_returns_exact_overnight_display_times`
   - `test_search_buses_returns_route_data_and_excludes_overlapping_seats`
3. `tests/test_chat_options.py` (5 tests - all passing):
   - Options payload formatting with `available seats` and no leaked internal UUIDs.
4. `tests/test_chat_components.py` (6 tests - all passing):
   - Server-side static HTML rendering via React/Node harness verifying no `Stop N · ` prefix, `available seats` wording, and sequence-based `aria-disabled="true"`.

### Frontend Checks
- `npx tsc --noEmit`: Exited with code 0 (zero type errors).
- `npm run lint`: Exited with code 0 (zero linting errors).
- `npm run build`: Production build succeeded in 10.6s.

### File Boundary Verification
- Git diff check on restricted files:
  ```bash
  git diff -- src/bus_booking_ai_agent/services/booking_service.py \
              src/bus_booking_ai_agent/services/hold_service.py \
              src/bus_booking_ai_agent/services/payment_service.py \
              schema.sql
  ```
  Result: Empty (zero lines changed).

