-- =============================================================================
-- Agentic AI Bus Ticket Booking Application
-- PostgreSQL reference queries for Supabase
--
-- Purpose:
--   These are the SQL queries that will support the future read-only MCP tools.
--
-- Important:
--   - These queries read from PostgreSQL. They do not read CSV files.
--   - Use parameterized values from the application. Do not build SQL with
--     string interpolation.
--   - $1, $2, ... are PostgreSQL positional parameters.
--   - bookings and booking_seats are intentionally empty until Supabase Auth
--     and the real booking flow are implemented.
--
-- Main future MCP tools:
--   1. search_buses
--   2. get_bus_details
--   3. check_seat_availability
--   4. get_booking
-- =============================================================================


-- =============================================================================
-- 01. SEARCH BUSES
-- =============================================================================
-- Parameters:
--   $1 = origin text
--   $2 = destination text
--   $3 = travel_date date
--
-- Returns one row per matching schedule, including:
--   operator, bus, bus type, departure/arrival time and fare.
--
-- The fare is selected for the requested route endpoints. Pricing is therefore
-- read from `fares`, not calculated from `bus_type`.

WITH requested_stops AS (
    SELECT
        r.id AS route_id,
        r.origin,
        r.destination,
        origin_stop.id AS boarding_stop_id,
        destination_stop.id AS dropping_stop_id
    FROM routes r
    JOIN route_stops origin_stop
        ON origin_stop.route_id = r.id
       AND origin_stop.stop_name = $1
       AND origin_stop.is_active = TRUE
       AND origin_stop.is_boarding_allowed = TRUE
    JOIN route_stops destination_stop
        ON destination_stop.route_id = r.id
       AND destination_stop.stop_name = $2
       AND destination_stop.is_active = TRUE
       AND destination_stop.is_dropping_allowed = TRUE
    WHERE r.origin = $1
      AND r.destination = $2
      AND r.is_active = TRUE
      AND origin_stop.sequence_number < destination_stop.sequence_number
)
SELECT
    s.id AS schedule_id,
    o.id AS operator_id,
    o.name AS operator_name,
    o.code AS operator_code,
    b.id AS bus_id,
    b.bus_number,
    b.bus_type,
    b.total_seats,
    b.amenities,
    r.id AS route_id,
    r.origin,
    r.destination,
    s.travel_date,
    boarding_schedule_stop.departure_time AS departure_time,
    dropping_schedule_stop.arrival_time AS arrival_time,
    f.amount AS fare_amount,
    f.currency
FROM schedules s
JOIN requested_stops rs
    ON rs.route_id = s.route_id
JOIN buses b
    ON b.id = s.bus_id
JOIN operators o
    ON o.id = b.operator_id
JOIN routes r
    ON r.id = s.route_id
JOIN schedule_stops boarding_schedule_stop
    ON boarding_schedule_stop.schedule_id = s.id
   AND boarding_schedule_stop.route_stop_id = rs.boarding_stop_id
JOIN schedule_stops dropping_schedule_stop
    ON dropping_schedule_stop.schedule_id = s.id
   AND dropping_schedule_stop.route_stop_id = rs.dropping_stop_id
JOIN fares f
    ON f.schedule_id = s.id
   AND f.boarding_stop_id = rs.boarding_stop_id
   AND f.dropping_stop_id = rs.dropping_stop_id
   AND f.is_active = TRUE
WHERE s.travel_date = $3
  AND s.status = 'SCHEDULED'
  AND b.is_active = TRUE
  AND o.is_active = TRUE
ORDER BY boarding_schedule_stop.departure_time, f.amount;


-- =============================================================================
-- 02. GET BUS / SCHEDULE DETAILS
-- =============================================================================
-- Parameter:
--   $1 = schedule_id uuid
--
-- Returns the scheduled bus, operator, route and schedule information.
-- Seat inventory is returned separately by query 06/07.

SELECT
    s.id AS schedule_id,
    s.travel_date,
    s.status,
    o.id AS operator_id,
    o.name AS operator_name,
    o.code AS operator_code,
    b.id AS bus_id,
    b.bus_number,
    b.bus_type,
    b.total_seats,
    b.amenities,
    r.id AS route_id,
    r.origin,
    r.destination,
    r.distance_km,
    r.estimated_duration_minutes
FROM schedules s
JOIN buses b
    ON b.id = s.bus_id
JOIN operators o
    ON o.id = b.operator_id
JOIN routes r
    ON r.id = s.route_id
WHERE s.id = $1;


-- =============================================================================
-- 03. GET ROUTE STOPS FOR A SCHEDULE
-- =============================================================================
-- Parameter:
--   $1 = schedule_id uuid
--
-- Returns the actual stops and times for this scheduled journey.

SELECT
    ss.id AS schedule_stop_id,
    rs.id AS route_stop_id,
    rs.stop_name,
    rs.sequence_number,
    ss.arrival_time,
    ss.departure_time,
    ss.is_boarding_allowed,
    ss.is_dropping_allowed
FROM schedule_stops ss
JOIN route_stops rs
    ON rs.id = ss.route_stop_id
WHERE ss.schedule_id = $1
ORDER BY rs.sequence_number;


-- =============================================================================
-- 04. GET BOARDING POINTS FOR A SCHEDULE
-- =============================================================================
-- Parameter:
--   $1 = schedule_id uuid
--
-- Useful when the user has selected a bus and wants to see valid boarding
-- points.

SELECT
    ss.route_stop_id,
    rs.stop_name,
    rs.sequence_number,
    ss.departure_time
FROM schedule_stops ss
JOIN route_stops rs
    ON rs.id = ss.route_stop_id
WHERE ss.schedule_id = $1
  AND ss.is_boarding_allowed = TRUE
  AND rs.is_active = TRUE
ORDER BY rs.sequence_number;


-- =============================================================================
-- 05. GET DROPPING POINTS FOR A SCHEDULE
-- =============================================================================
-- Parameter:
--   $1 = schedule_id uuid
--
-- Useful when the user has selected a bus and wants to see valid dropping
-- points.

SELECT
    ss.route_stop_id,
    rs.stop_name,
    rs.sequence_number,
    ss.arrival_time
FROM schedule_stops ss
JOIN route_stops rs
    ON rs.id = ss.route_stop_id
WHERE ss.schedule_id = $1
  AND ss.is_dropping_allowed = TRUE
  AND rs.is_active = TRUE
ORDER BY rs.sequence_number;


-- =============================================================================
-- 06. GET ALL PHYSICAL SEATS FOR A SCHEDULE
-- =============================================================================
-- Parameter:
--   $1 = schedule_id uuid
--
-- A schedule uses the physical seats belonging to its bus.

SELECT
    bs.id AS seat_id,
    bs.seat_number,
    bs.seat_type,
    bs.row_number,
    bs.column_number,
    bs.is_active
FROM schedules s
JOIN bus_seats bs
    ON bs.bus_id = s.bus_id
WHERE s.id = $1
  AND bs.is_active = TRUE
ORDER BY bs.row_number NULLS LAST,
         bs.column_number NULLS LAST,
         bs.seat_number;


-- =============================================================================
-- 07. CHECK SEAT AVAILABILITY FOR A JOURNEY SEGMENT
-- =============================================================================
-- Parameters:
--   $1 = schedule_id uuid
--   $2 = boarding_stop_id uuid
--   $3 = dropping_stop_id uuid
--
-- Important:
--   Seat availability is NOT stored on bus_seats.
--
--   A seat is unavailable when a CONFIRMED booking for the same schedule
--   uses that seat and its journey segment overlaps the requested segment.
--
--   The overlap rule uses route-stop sequence:
--
--       existing boarding < requested dropping
--       AND
--       existing dropping > requested boarding
--
--   This allows a seat to be reused after an existing passenger gets off.
--
--   Example:
--       Existing: Hyderabad -> Kurnool
--       Requested: Kurnool -> Bangalore
--       No overlap, so the seat can be available.
--
--       Existing: Hyderabad -> Bangalore
--       Requested: Kurnool -> Bangalore
--       Overlap, so the seat is unavailable.
--
-- This query is intentionally written against the future real booking data.
-- With zero bookings, all active physical seats are returned as available.

WITH requested_segment AS (
    SELECT
        s.id AS schedule_id,
        boarding.sequence_number AS boarding_sequence,
        dropping.sequence_number AS dropping_sequence
    FROM schedules s
    JOIN route_stops boarding
        ON boarding.id = $2
       AND boarding.route_id = s.route_id
    JOIN route_stops dropping
        ON dropping.id = $3
       AND dropping.route_id = s.route_id
    WHERE s.id = $1
      AND boarding.is_boarding_allowed = TRUE
      AND dropping.is_dropping_allowed = TRUE
      AND boarding.sequence_number < dropping.sequence_number
)
SELECT
    bs.id AS seat_id,
    bs.seat_number,
    bs.seat_type,
    bs.row_number,
    bs.column_number
FROM schedules s
JOIN bus_seats bs
    ON bs.bus_id = s.bus_id
JOIN requested_segment rs
    ON rs.schedule_id = s.id
WHERE bs.is_active = TRUE
  AND NOT EXISTS (
      SELECT 1
      FROM booking_seats booked_seat
      JOIN bookings booking
          ON booking.id = booked_seat.booking_id
      JOIN route_stops existing_boarding
          ON existing_boarding.id = booking.boarding_stop_id
      JOIN route_stops existing_dropping
          ON existing_dropping.id = booking.dropping_stop_id
      WHERE booking.schedule_id = s.id
        AND booking.status = 'CONFIRMED'
        AND booked_seat.seat_id = bs.id
        AND existing_boarding.route_id = s.route_id
        AND existing_dropping.route_id = s.route_id
        AND existing_boarding.sequence_number < rs.dropping_sequence
        AND existing_dropping.sequence_number > rs.boarding_sequence
  )
ORDER BY bs.row_number NULLS LAST,
         bs.column_number NULLS LAST,
         bs.seat_number;


-- =============================================================================
-- 08. COUNT AVAILABLE SEATS FOR A JOURNEY SEGMENT
-- =============================================================================
-- Parameters:
--   $1 = schedule_id uuid
--   $2 = boarding_stop_id uuid
--   $3 = dropping_stop_id uuid
--
-- Same availability rule as query 07, but returns only the count.

WITH requested_segment AS (
    SELECT
        s.id AS schedule_id,
        boarding.sequence_number AS boarding_sequence,
        dropping.sequence_number AS dropping_sequence
    FROM schedules s
    JOIN route_stops boarding
        ON boarding.id = $2
       AND boarding.route_id = s.route_id
    JOIN route_stops dropping
        ON dropping.id = $3
       AND dropping.route_id = s.route_id
    WHERE s.id = $1
      AND boarding.is_boarding_allowed = TRUE
      AND dropping.is_dropping_allowed = TRUE
      AND boarding.sequence_number < dropping.sequence_number
)
SELECT
    COUNT(*) AS available_seat_count
FROM schedules s
JOIN bus_seats bs
    ON bs.bus_id = s.bus_id
JOIN requested_segment rs
    ON rs.schedule_id = s.id
WHERE bs.is_active = TRUE
  AND NOT EXISTS (
      SELECT 1
      FROM booking_seats booked_seat
      JOIN bookings booking
          ON booking.id = booked_seat.booking_id
      JOIN route_stops existing_boarding
          ON existing_boarding.id = booking.boarding_stop_id
      JOIN route_stops existing_dropping
          ON existing_dropping.id = booking.dropping_stop_id
      WHERE booking.schedule_id = s.id
        AND booking.status = 'CONFIRMED'
        AND booked_seat.seat_id = bs.id
        AND existing_boarding.route_id = s.route_id
        AND existing_dropping.route_id = s.route_id
        AND existing_boarding.sequence_number < rs.dropping_sequence
        AND existing_dropping.sequence_number > rs.boarding_sequence
  );


-- =============================================================================
-- 09. GET FARE FOR A SPECIFIC JOURNEY SEGMENT
-- =============================================================================
-- Parameters:
--   $1 = schedule_id uuid
--   $2 = boarding_stop_id uuid
--   $3 = dropping_stop_id uuid
--
-- Returns the explicitly stored fare.
-- No bus-type-based price calculation is performed.

SELECT
    f.id AS fare_id,
    f.schedule_id,
    f.boarding_stop_id,
    boarding.stop_name AS boarding_point,
    f.dropping_stop_id,
    dropping.stop_name AS dropping_point,
    f.amount,
    f.currency
FROM fares f
JOIN route_stops boarding
    ON boarding.id = f.boarding_stop_id
JOIN route_stops dropping
    ON dropping.id = f.dropping_stop_id
WHERE f.schedule_id = $1
  AND f.boarding_stop_id = $2
  AND f.dropping_stop_id = $3
  AND f.is_active = TRUE;


-- =============================================================================
-- 10. GET BOOKING BY REFERENCE
-- =============================================================================
-- Parameter:
--   $1 = booking_reference text
--
-- This query is included for the future get_booking MCP tool.
-- It will return no rows until real bookings are created.

SELECT
    b.id AS booking_id,
    b.booking_reference,
    b.auth_user_id,
    b.schedule_id,
    b.boarding_stop_id,
    boarding.stop_name AS boarding_point,
    b.dropping_stop_id,
    dropping.stop_name AS dropping_point,
    b.passenger_count,
    b.total_amount,
    b.status,
    b.booked_at,
    b.cancelled_at,
    s.travel_date,
    o.name AS operator_name,
    bus.bus_number,
    bus.bus_type,
    r.origin,
    r.destination
FROM bookings b
JOIN route_stops boarding
    ON boarding.id = b.boarding_stop_id
JOIN route_stops dropping
    ON dropping.id = b.dropping_stop_id
JOIN schedules s
    ON s.id = b.schedule_id
JOIN buses bus
    ON bus.id = s.bus_id
JOIN operators o
    ON o.id = bus.operator_id
JOIN routes r
    ON r.id = s.route_id
WHERE b.booking_reference = $1;


-- =============================================================================
-- 11. GET BOOKING PASSENGERS AND SEATS
-- =============================================================================
-- Parameter:
--   $1 = booking_id uuid
--
-- This is a supporting query for get_booking.

SELECT
    bs.id AS booking_seat_id,
    bs.booking_id,
    bs.seat_id,
    physical_seat.seat_number,
    physical_seat.seat_type,
    bs.passenger_name,
    bs.passenger_age,
    bs.passenger_gender,
    bs.fare
FROM booking_seats bs
JOIN bus_seats physical_seat
    ON physical_seat.id = bs.seat_id
WHERE bs.booking_id = $1
ORDER BY physical_seat.seat_number;


-- =============================================================================
-- 12. GET BUS SEAT LAYOUT
-- =============================================================================
-- Parameter:
--   $1 = bus_id uuid
--
-- Useful for displaying the physical seat layout before schedule-specific
-- availability is calculated.

SELECT
    id AS seat_id,
    seat_number,
    seat_type,
    row_number,
    column_number,
    is_active
FROM bus_seats
WHERE bus_id = $1
ORDER BY row_number NULLS LAST,
         column_number NULLS LAST,
         seat_number;


-- =============================================================================
-- 13. FIND SCHEDULES FOR A ROUTE AND DATE
-- =============================================================================
-- Parameters:
--   $1 = route_id uuid
--   $2 = travel_date date
--
-- Lower-level supporting query for search_buses.

SELECT
    s.id AS schedule_id,
    s.bus_id,
    s.route_id,
    s.travel_date,
    s.status,
    o.id AS operator_id,
    o.name AS operator_name,
    b.bus_number,
    b.bus_type,
    b.total_seats
FROM schedules s
JOIN buses b
    ON b.id = s.bus_id
JOIN operators o
    ON o.id = b.operator_id
WHERE s.route_id = $1
  AND s.travel_date = $2
  AND s.status = 'SCHEDULED'
  AND b.is_active = TRUE
  AND o.is_active = TRUE
ORDER BY o.name, b.bus_number;


-- =============================================================================
-- 14. VERIFY OPERATOR COVERAGE PER ROUTE
-- =============================================================================
-- No parameters.
--
-- Development/validation query.
-- Expected result: exactly 5 operators for each of the 5 routes.

SELECT
    r.id AS route_id,
    r.origin,
    r.destination,
    COUNT(DISTINCT b.operator_id) AS operator_count
FROM routes r
JOIN schedules s
    ON s.route_id = r.id
JOIN buses b
    ON b.id = s.bus_id
JOIN operators o
    ON o.id = b.operator_id
WHERE s.status = 'SCHEDULED'
GROUP BY r.id, r.origin, r.destination
ORDER BY r.origin, r.destination;


-- =============================================================================
-- 15. VERIFY DATABASE ROW COUNTS
-- =============================================================================
-- No parameters.
--
-- Development/validation query.

SELECT 'operators' AS table_name, COUNT(*) AS row_count FROM operators
UNION ALL
SELECT 'buses', COUNT(*) FROM buses
UNION ALL
SELECT 'bus_seats', COUNT(*) FROM bus_seats
UNION ALL
SELECT 'routes', COUNT(*) FROM routes
UNION ALL
SELECT 'route_stops', COUNT(*) FROM route_stops
UNION ALL
SELECT 'schedules', COUNT(*) FROM schedules
UNION ALL
SELECT 'schedule_stops', COUNT(*) FROM schedule_stops
UNION ALL
SELECT 'fares', COUNT(*) FROM fares
UNION ALL
SELECT 'bookings', COUNT(*) FROM bookings
UNION ALL
SELECT 'booking_seats', COUNT(*) FROM booking_seats
ORDER BY table_name;


-- =============================================================================
-- 16. FIND ORPHANED / INVALID SCHEDULE STOPS
-- =============================================================================
-- No parameters.
--
-- Development/validation query.
-- Should return zero rows.
--
-- This checks the cross-table rule that a schedule_stop's route_stop belongs
-- to the same route as the schedule.

SELECT
    ss.id AS schedule_stop_id,
    ss.schedule_id,
    ss.route_stop_id,
    s.route_id AS schedule_route_id,
    rs.route_id AS stop_route_id
FROM schedule_stops ss
JOIN schedules s
    ON s.id = ss.schedule_id
JOIN route_stops rs
    ON rs.id = ss.route_stop_id
WHERE s.route_id <> rs.route_id;


-- =============================================================================
-- 17. FIND INVALID FARES
-- =============================================================================
-- No parameters.
--
-- Should return zero rows.
--
-- Checks that:
--   - fare stops belong to the schedule route
--   - boarding comes before dropping

SELECT
    f.id AS fare_id,
    f.schedule_id,
    f.boarding_stop_id,
    f.dropping_stop_id,
    s.route_id AS schedule_route_id,
    boarding.route_id AS boarding_route_id,
    dropping.route_id AS dropping_route_id,
    boarding.sequence_number AS boarding_sequence,
    dropping.sequence_number AS dropping_sequence
FROM fares f
JOIN schedules s
    ON s.id = f.schedule_id
JOIN route_stops boarding
    ON boarding.id = f.boarding_stop_id
JOIN route_stops dropping
    ON dropping.id = f.dropping_stop_id
WHERE boarding.route_id <> s.route_id
   OR dropping.route_id <> s.route_id
   OR boarding.sequence_number >= dropping.sequence_number;


-- =============================================================================
-- 18. FIND BUS SEAT COUNT MISMATCHES
-- =============================================================================
-- No parameters.
--
-- Should return zero rows.
--
-- Ensures buses.total_seats agrees with the number of active physical seats.

SELECT
    b.id AS bus_id,
    b.bus_number,
    b.total_seats,
    COUNT(bs.id) AS actual_active_seats
FROM buses b
LEFT JOIN bus_seats bs
    ON bs.bus_id = b.id
   AND bs.is_active = TRUE
GROUP BY b.id, b.bus_number, b.total_seats
HAVING COUNT(bs.id) <> b.total_seats
ORDER BY b.bus_number;


-- =============================================================================
-- 19. FIND DUPLICATE / MISSING SCHEDULE STOP COUNTS
-- =============================================================================
-- No parameters.
--
-- Each schedule should have the same number of schedule_stops as its route
-- has route_stops.

SELECT
    s.id AS schedule_id,
    r.origin,
    r.destination,
    route_stop_count.expected_stop_count,
    COUNT(ss.id) AS actual_stop_count
FROM schedules s
JOIN routes r
    ON r.id = s.route_id
JOIN (
    SELECT
        route_id,
        COUNT(*) AS expected_stop_count
    FROM route_stops
    WHERE is_active = TRUE
    GROUP BY route_id
) route_stop_count
    ON route_stop_count.route_id = s.route_id
LEFT JOIN schedule_stops ss
    ON ss.schedule_id = s.id
GROUP BY
    s.id,
    r.origin,
    r.destination,
    route_stop_count.expected_stop_count
HAVING COUNT(ss.id) <> route_stop_count.expected_stop_count
ORDER BY r.origin, r.destination;


-- =============================================================================
-- NOTES FOR THE FUTURE MCP IMPLEMENTATION
-- =============================================================================
--
-- search_buses
--   Primary query: 01
--
-- get_bus_details
--   Primary query: 02
--   Supporting queries: 03, 04, 05, 06
--
-- check_seat_availability
--   Primary query: 07
--   Optional count query: 08
--
-- get_booking
--   Primary query: 10
--   Supporting query: 11
--
-- Development validation
--   Queries: 14, 15, 16, 17, 18, 19
--
-- The SQL file is a reference/query layer. The MCP tools will eventually call
-- parameterized SQL through the application's database connection.
--
-- Do not connect Gemini directly to PostgreSQL.
-- Do not let Gemini generate arbitrary SQL for the runtime booking workflow.
-- The application should expose controlled tools backed by deterministic SQL.
-- =============================================================================
