-- Required for gen_random_uuid()
create extension if not exists pgcrypto;

-- =============================================================================
-- 1. OPERATORS
-- =============================================================================
create table operators (
    id             uuid primary key default gen_random_uuid(),
    name           text not null,
    code           text not null unique,
    contact_phone  text,
    email          text,
    is_active      boolean not null default true,
    created_at     timestamptz not null default now()
);

-- =============================================================================
-- 2. BUSES
-- =============================================================================
create table buses (
    id             uuid primary key default gen_random_uuid(),
    operator_id    uuid not null references operators (id),
    bus_number     text not null unique,
    bus_type       text not null,
    total_seats    integer not null check (total_seats > 0),
    -- JSONB: multiple amenities per bus, e.g. ["AC","WiFi","Charging Point"]
    amenities      jsonb not null default '[]'::jsonb,
    is_active      boolean not null default true,
    created_at     timestamptz not null default now(),
    constraint buses_bus_type_check check (
        bus_type in (
            'AC Sleeper', 'Non-AC Sleeper', 'AC Seater',
            'Non-AC Seater', 'Volvo AC', 'AC Semi-Sleeper'
        )
    )
    -- Intentionally NOT storing price here: bus_type is a physical/service
    -- attribute, never a price determinant. See `fares`.
);

-- =============================================================================
-- 3. BUS_SEATS
-- =============================================================================
create table bus_seats (
    id             uuid primary key default gen_random_uuid(),
    bus_id         uuid not null references buses (id),
    seat_number    text not null,
    seat_type      text not null,
    row_number     integer,
    column_number  integer,
    is_active      boolean not null default true,
    created_at     timestamptz not null default now(),
    constraint bus_seats_seat_type_check check (seat_type in ('SEATER', 'LOWER', 'UPPER')),
    constraint bus_seats_bus_id_seat_number_key unique (bus_id, seat_number)
    -- No is_available column: availability is derived per-schedule from
    -- `booking_seats`, not stored on the physical seat.
);

-- =============================================================================
-- 4. ROUTES
-- =============================================================================
create table routes (
    id                          uuid primary key default gen_random_uuid(),
    origin                      text not null,
    destination                 text not null,
    distance_km                 numeric not null check (distance_km > 0),
    estimated_duration_minutes  integer not null check (estimated_duration_minutes > 0),
    is_active                   boolean not null default true,
    created_at                  timestamptz not null default now(),
    constraint routes_origin_destination_check check (origin <> destination)
    -- No boarding_point / dropping_point columns here: a route has many
    -- stops, modeled in `route_stops`.
);

-- =============================================================================
-- 5. ROUTE_STOPS
-- =============================================================================
create table route_stops (
    id                    uuid primary key default gen_random_uuid(),
    route_id              uuid not null references routes (id),
    stop_name             text not null,
    sequence_number       integer not null,
    is_boarding_allowed   boolean not null default true,
    is_dropping_allowed   boolean not null default true,
    is_active             boolean not null default true,
    created_at            timestamptz not null default now(),
    constraint route_stops_route_id_sequence_number_key unique (route_id, sequence_number)
);

-- =============================================================================
-- 6. SCHEDULES
-- =============================================================================
create table schedules (
    id           uuid primary key default gen_random_uuid(),
    bus_id       uuid not null references buses (id),
    route_id     uuid not null references routes (id),
    travel_date  date not null,
    status       text not null,
    created_at   timestamptz not null default now(),
    constraint schedules_status_check check (status in ('SCHEDULED', 'CANCELLED', 'COMPLETED')),
    -- Prevents an accidental duplicate journey occurrence for the same bus,
    -- route and date.
    constraint schedules_bus_route_date_key unique (bus_id, route_id, travel_date)
    -- No boarding_point / dropping_point / price columns here by design.
);

-- =============================================================================
-- 7. SCHEDULE_STOPS
-- =============================================================================
create table schedule_stops (
    id                   uuid primary key default gen_random_uuid(),
    schedule_id          uuid not null references schedules (id),
    route_stop_id        uuid not null references route_stops (id),
    arrival_time         time not null,
    departure_time       time not null,
    is_boarding_allowed  boolean not null,
    is_dropping_allowed  boolean not null,
    created_at           timestamptz not null default now(),
    constraint schedule_stops_schedule_id_route_stop_id_key unique (schedule_id, route_stop_id)
    -- See header note: route_stop_id's route must match schedule.route_id.
    -- Enforced in the service layer.
);

-- =============================================================================
-- 8. FARES
-- =============================================================================
create table fares (
    id                 uuid primary key default gen_random_uuid(),
    schedule_id        uuid not null references schedules (id),
    boarding_stop_id   uuid not null references route_stops (id),
    dropping_stop_id   uuid not null references route_stops (id),
    amount             numeric(10, 2) not null check (amount > 0),
    currency           text not null default 'INR',
    is_active          boolean not null default true,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now(),
    constraint fares_boarding_dropping_distinct_check check (boarding_stop_id <> dropping_stop_id),
    constraint fares_schedule_boarding_dropping_key unique (schedule_id, boarding_stop_id, dropping_stop_id)
    -- See header note: boarding stop's sequence must precede dropping stop's
    -- sequence on the shared route, and both must belong to schedule's route.
    -- Enforced in the service layer (and true by construction in seed data).
    --
    -- Fare is deliberately NOT derived from bus_type. It is stored explicitly
    -- per (schedule, boarding_stop, dropping_stop) so it can vary freely by
    -- operator, schedule and segment distance.
);

-- =============================================================================
-- 9. BOOKINGS  (schema only — table stays empty until Supabase Auth ships)
-- =============================================================================
create table bookings (
    id                 uuid primary key default gen_random_uuid(),
    booking_reference  text not null unique,
    -- References the Supabase Auth user (auth.users.id). No local FK is
    -- created because there is no local `users` table — auth is out of
    -- scope for this migration and will be added later.
    auth_user_id       uuid not null,
    schedule_id        uuid not null references schedules (id),
    boarding_stop_id   uuid not null references route_stops (id),
    dropping_stop_id   uuid not null references route_stops (id),
    passenger_count    integer not null check (passenger_count > 0),
    total_amount       numeric(10, 2) not null check (total_amount >= 0),
    status             text not null,
    booked_at          timestamptz not null default now(),
    cancelled_at       timestamptz,
    created_at         timestamptz not null default now(),
    constraint bookings_status_check check (status in ('CONFIRMED', 'CANCELLED'))
);

-- =============================================================================
-- 10. BOOKING_SEATS  (schema only — table stays empty until real bookings exist)
-- =============================================================================
create table booking_seats (
    id                uuid primary key default gen_random_uuid(),
    booking_id        uuid not null references bookings (id),
    seat_id           uuid not null references bus_seats (id),
    passenger_name    text not null,
    passenger_age     integer not null check (passenger_age > 0),
    passenger_gender  text not null,
    fare              numeric(10, 2) not null check (fare >= 0),
    created_at        timestamptz not null default now(),
    constraint booking_seats_gender_check check (passenger_gender in ('MALE', 'FEMALE', 'OTHER')),
    constraint booking_seats_booking_id_seat_id_key unique (booking_id, seat_id)
);


-- ============================================================
-- HOLD STATUS
-- ============================================================

CREATE TYPE hold_status AS ENUM (
    'ACTIVE',
    'RELEASED',
    'EXPIRED',
    'CONVERTED'
);


-- ============================================================
-- SEAT HOLDS
-- ============================================================

CREATE TABLE seat_holds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Real Supabase Auth user UUID.
    -- This is supplied by the authenticated backend context,
    -- never by Gemini or the browser request body.
    auth_user_id UUID NOT NULL,

    -- Scheduled bus journey
    schedule_id UUID NOT NULL,

    -- Physical seat on the bus
    seat_id UUID NOT NULL,

    -- Journey segment
    boarding_stop_id UUID NOT NULL,
    dropping_stop_id UUID NOT NULL,

    -- Validated route-stop sequence numbers.
    -- These are derived from the database during hold creation.
    boarding_sequence INTEGER NOT NULL,
    dropping_sequence INTEGER NOT NULL,

    -- Hold lifecycle
    status hold_status NOT NULL DEFAULT 'ACTIVE',

    -- Hold expiration
    expires_at TIMESTAMPTZ NOT NULL,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    released_at TIMESTAMPTZ,
    converted_at TIMESTAMPTZ,

    -- Set when the hold becomes a confirmed booking.
    booking_id UUID,

    -- ========================================================
    -- CHECK CONSTRAINTS
    -- ========================================================

    CONSTRAINT seat_holds_valid_sequence
        CHECK (
            boarding_sequence < dropping_sequence
        ),

    CONSTRAINT seat_holds_valid_expiration
        CHECK (
            expires_at > created_at
        ),

    CONSTRAINT seat_holds_released_timestamp
        CHECK (
            status <> 'RELEASED'
            OR released_at IS NOT NULL
        ),

    CONSTRAINT seat_holds_converted_timestamp
        CHECK (
            status <> 'CONVERTED'
            OR converted_at IS NOT NULL
        ),

    CONSTRAINT seat_holds_converted_booking
        CHECK (
            status <> 'CONVERTED'
            OR booking_id IS NOT NULL
        ),

    -- ========================================================
    -- FOREIGN KEYS
    -- ========================================================

    CONSTRAINT seat_holds_schedule_fk
        FOREIGN KEY (schedule_id)
        REFERENCES schedules(id),

    CONSTRAINT seat_holds_seat_fk
        FOREIGN KEY (seat_id)
        REFERENCES bus_seats(id),

    CONSTRAINT seat_holds_boarding_stop_fk
        FOREIGN KEY (boarding_stop_id)
        REFERENCES route_stops(id),

    CONSTRAINT seat_holds_dropping_stop_fk
        FOREIGN KEY (dropping_stop_id)
        REFERENCES route_stops(id),

    CONSTRAINT seat_holds_booking_fk
        FOREIGN KEY (booking_id)
        REFERENCES bookings(id)
);


-- =============================================================================
-- INDEXES  (for the read-only MCP tools: search_buses, get_bus_details,
-- check_seat_availability, get_booking)
-- =============================================================================
create index idx_schedules_route_id on schedules (route_id);
create index idx_schedules_bus_id on schedules (bus_id);
create index idx_schedules_travel_date on schedules (travel_date);
create index idx_schedules_status on schedules (status);

create index idx_route_stops_route_id on route_stops (route_id);

create index idx_schedule_stops_schedule_id on schedule_stops (schedule_id);
create index idx_schedule_stops_route_stop_id on schedule_stops (route_stop_id);

create index idx_fares_schedule_id on fares (schedule_id);
create index idx_fares_boarding_stop_id on fares (boarding_stop_id);
create index idx_fares_dropping_stop_id on fares (dropping_stop_id);

create index idx_bus_seats_bus_id on bus_seats (bus_id);

create index idx_bookings_auth_user_id on bookings (auth_user_id);
create index idx_bookings_schedule_id on bookings (schedule_id);
create index idx_bookings_status on bookings (status);

create index idx_booking_seats_booking_id on booking_seats (booking_id);
create index idx_booking_seats_seat_id on booking_seats (seat_id);


CREATE INDEX idx_seat_holds_schedule_seat
    ON seat_holds(schedule_id, seat_id);

CREATE INDEX idx_seat_holds_user
    ON seat_holds(auth_user_id);

CREATE INDEX idx_seat_holds_status_expiration
    ON seat_holds(status, expires_at);

CREATE INDEX idx_seat_holds_schedule_segment
    ON seat_holds(
        schedule_id,
        seat_id,
        boarding_sequence,
        dropping_sequence
    );

CREATE INDEX idx_seat_holds_booking
    ON seat_holds(booking_id);
