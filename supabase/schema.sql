-- ==============================================================================
-- College Concert Ticket Booking Platform Database Schema
-- Concurrency Architecture: Row Locks + Advisory Locks + Partial Unique Indexes
-- ==============================================================================

-- Clean up any legacy UUID-based functions if migrating from older schema
drop function if exists public.reserve_seat(uuid, integer, text, integer);
drop function if exists public.get_reservation(uuid, uuid);
drop function if exists public.confirm_reservation(uuid, uuid);
drop function if exists public.fail_payment(uuid, uuid);
drop function if exists public.cancel_reservation(uuid, uuid);
drop function if exists public.booking_history(uuid);

-- Drop legacy UUID-based reservations table if it exists
drop table if exists public.reservations cascade;

create table if not exists public.seats (
    id integer primary key check (id between 1 and 500),
    label text not null unique
);

-- Seed 500 numbered concert seats
insert into public.seats (id, label)
select generated.n, 'Seat ' || lpad(generated.n::text, 3, '0')
from generate_series(1, 500) as generated(n)
on conflict (id) do nothing;

create table if not exists public.reservations (
    id bigint generated always as identity primary key,
    seat_id integer not null references public.seats(id),
    user_id bigint not null,
    idempotency_key text not null check (length(idempotency_key) between 1 and 128),
    status text not null check (
        status in ('reserved', 'confirmed', 'cancelled', 'expired', 'payment_failed')
    ),
    created_at timestamptz not null default now(),
    expires_at timestamptz,
    confirmed_at timestamptz,
    unique (user_id, idempotency_key)
);

-- Crucial: Prevents two active bookings (reserved or confirmed) on the same seat
create unique index if not exists one_live_booking_per_seat
on public.reservations (seat_id)
where status in ('reserved', 'confirmed');

-- Index for fast user booking history queries
create index if not exists reservations_by_user
on public.reservations (user_id, created_at desc);

-- Index for high-speed expiration sweeps
create index if not exists idx_reservations_active_expires
on public.reservations (expires_at)
where status = 'reserved';

-- ------------------------------------------------------------------------------
-- 1. List Seats (Optimized single-pass LEFT JOIN)
-- ------------------------------------------------------------------------------
create or replace function public.list_seats(p_available_only boolean default false)
returns jsonb
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    with seat_status as (
        select
            s.id,
            s.label,
            (r.id is null) as available
        from public.seats s
        left join public.reservations r
            on r.seat_id = s.id
           and (
               r.status = 'confirmed'
               or (r.status = 'reserved' and r.expires_at > now())
           )
    )
    select coalesce(jsonb_agg(jsonb_build_object(
        'id', ss.id,
        'label', ss.label,
        'available', ss.available
    ) order by ss.id), '[]'::jsonb)
    from seat_status ss
    where not p_available_only or ss.available = true;
$$;

-- ------------------------------------------------------------------------------
-- 2. Reserve Seat (Atomic Idempotent Lock & Hold)
-- ------------------------------------------------------------------------------
create or replace function public.reserve_seat(
    p_user_id bigint,
    p_seat_id integer,
    p_idempotency_key text,
    p_hold_seconds integer default 300
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_reservation public.reservations%rowtype;
begin
    if p_hold_seconds < 1 or p_hold_seconds > 900 then
        return jsonb_build_object('error', 'invalid_hold_duration');
    end if;

    -- Advisory lock prevents duplicate concurrent submissions with the exact same idempotency key
    perform pg_advisory_xact_lock(hashtextextended(p_user_id::text || ':' || p_idempotency_key, 0));

    -- Check if this idempotent request has already been recorded
    select * into v_reservation
    from public.reservations
    where user_id = p_user_id and idempotency_key = p_idempotency_key;

    if found then
        if v_reservation.status = 'reserved'
           and v_reservation.expires_at <= clock_timestamp() then
            return to_jsonb(v_reservation) || jsonb_build_object('status', 'expired');
        end if;
        return to_jsonb(v_reservation);
    end if;

    -- Acquire exclusive row lock on the seat to serialize concurrent attempts on this seat
    perform 1 from public.seats where id = p_seat_id for update;
    if not found then
        return jsonb_build_object('error', 'seat_not_found');
    end if;

    -- Atomically lazy-expire any existing hold that has lapsed
    update public.reservations
    set status = 'expired'
    where seat_id = p_seat_id
      and status = 'reserved'
      and expires_at <= clock_timestamp();

    -- Ensure no other active reservation or confirmed booking currently holds the seat
    if exists (
        select 1 from public.reservations
        where seat_id = p_seat_id
          and (status = 'confirmed' or (status = 'reserved' and expires_at > clock_timestamp()))
    ) then
        return jsonb_build_object('error', 'seat_unavailable');
    end if;

    -- Insert fresh temporary reservation
    insert into public.reservations (
        seat_id, user_id, idempotency_key, status, expires_at
    ) values (
        p_seat_id, p_user_id, p_idempotency_key, 'reserved',
        clock_timestamp() + make_interval(secs => p_hold_seconds)
    )
    returning * into v_reservation;

    return to_jsonb(v_reservation);
end;
$$;

-- ------------------------------------------------------------------------------
-- 3. Get Reservation Status
-- ------------------------------------------------------------------------------
create or replace function public.get_reservation(
    p_reservation_id bigint,
    p_user_id bigint default null
)
returns jsonb
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
    v_reservation public.reservations%rowtype;
begin
    select * into v_reservation
    from public.reservations
    where id = p_reservation_id
      and (p_user_id is null or user_id = p_user_id);

    if not found then
        return jsonb_build_object('error', 'reservation_not_found');
    end if;

    if v_reservation.status = 'reserved' and v_reservation.expires_at <= now() then
        return to_jsonb(v_reservation) || jsonb_build_object('status', 'expired');
    end if;

    return to_jsonb(v_reservation);
end;
$$;

-- ------------------------------------------------------------------------------
-- 4. Confirm Reservation (Payment Success)
-- ------------------------------------------------------------------------------
create or replace function public.confirm_reservation(
    p_reservation_id bigint,
    p_user_id bigint
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_seat_id integer;
    v_reservation public.reservations%rowtype;
begin
    select seat_id into v_seat_id
    from public.reservations
    where id = p_reservation_id and user_id = p_user_id;
    if not found then
        return jsonb_build_object('error', 'reservation_not_found');
    end if;

    -- Lock in consistent order: Seat row first, then reservation row
    perform 1 from public.seats where id = v_seat_id for update;
    select * into v_reservation
    from public.reservations
    where id = p_reservation_id and user_id = p_user_id
    for update;

    if v_reservation.status <> 'reserved' then
        if v_reservation.status = 'confirmed' then
            return to_jsonb(v_reservation);
        end if;
        return jsonb_build_object('error', 'not_reservable');
    end if;

    if v_reservation.expires_at <= clock_timestamp() then
        update public.reservations set status = 'expired' where id = p_reservation_id
        returning * into v_reservation;
        return jsonb_build_object('error', 'reservation_expired');
    end if;

    update public.reservations
    set status = 'confirmed', confirmed_at = now(), expires_at = null
    where id = p_reservation_id
    returning * into v_reservation;

    return to_jsonb(v_reservation);
end;
$$;

-- ------------------------------------------------------------------------------
-- 5. Fail Payment
-- ------------------------------------------------------------------------------
create or replace function public.fail_payment(
    p_reservation_id bigint,
    p_user_id bigint
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_seat_id integer;
    v_reservation public.reservations%rowtype;
begin
    select seat_id into v_seat_id
    from public.reservations
    where id = p_reservation_id and user_id = p_user_id;
    if not found then
        return jsonb_build_object('error', 'reservation_not_found');
    end if;

    perform 1 from public.seats where id = v_seat_id for update;
    select * into v_reservation
    from public.reservations
    where id = p_reservation_id and user_id = p_user_id
    for update;

    if v_reservation.status <> 'reserved' then
        if v_reservation.status = 'payment_failed' then
            return to_jsonb(v_reservation);
        end if;
        return jsonb_build_object('error', 'payment_not_pending');
    end if;

    if v_reservation.expires_at <= clock_timestamp() then
        update public.reservations set status = 'expired' where id = p_reservation_id
        returning * into v_reservation;
        return jsonb_build_object('error', 'reservation_expired');
    end if;

    update public.reservations set status = 'payment_failed', expires_at = null
    where id = p_reservation_id
    returning * into v_reservation;

    return to_jsonb(v_reservation);
end;
$$;

-- ------------------------------------------------------------------------------
-- 6. Cancel Reservation
-- ------------------------------------------------------------------------------
create or replace function public.cancel_reservation(
    p_reservation_id bigint,
    p_user_id bigint
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_seat_id integer;
    v_reservation public.reservations%rowtype;
begin
    select seat_id into v_seat_id
    from public.reservations
    where id = p_reservation_id and user_id = p_user_id;
    if not found then
        return jsonb_build_object('error', 'reservation_not_found');
    end if;

    perform 1 from public.seats where id = v_seat_id for update;
    select * into v_reservation
    from public.reservations
    where id = p_reservation_id and user_id = p_user_id
    for update;

    if v_reservation.status not in ('reserved', 'confirmed') then
        if v_reservation.status = 'cancelled' then
            return to_jsonb(v_reservation);
        end if;
        return jsonb_build_object('error', 'invalid_transition');
    end if;

    update public.reservations set status = 'cancelled', expires_at = null
    where id = p_reservation_id
    returning * into v_reservation;

    return to_jsonb(v_reservation);
end;
$$;

-- ------------------------------------------------------------------------------
-- 7. Booking History
-- ------------------------------------------------------------------------------
create or replace function public.booking_history(p_user_id bigint)
returns jsonb
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select coalesce(jsonb_agg(
        jsonb_set(
            to_jsonb(r),
            '{status}',
            to_jsonb(case
                when r.status = 'reserved' and r.expires_at <= now()
                    then 'expired'
                else r.status
            end)
        )
        order by r.created_at desc
    ), '[]'::jsonb)
    from public.reservations r
    where r.user_id = p_user_id;
$$;

-- ------------------------------------------------------------------------------
-- 8. Bulk Expiration Maintenance (Optional background cleaner)
-- ------------------------------------------------------------------------------
create or replace function public.cleanup_expired_reservations()
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_count integer;
begin
    with updated as (
        update public.reservations
        set status = 'expired'
        where status = 'reserved'
          and expires_at <= clock_timestamp()
        returning 1
    )
    select count(*) into v_count from updated;
    return v_count;
end;
$$;

-- ------------------------------------------------------------------------------
-- Security & Permissions
-- ------------------------------------------------------------------------------
alter table public.seats enable row level security;
alter table public.reservations enable row level security;
revoke all on table public.seats, public.reservations from anon, authenticated;

revoke all on function public.list_seats(boolean) from public, anon, authenticated;
revoke all on function public.reserve_seat(bigint, integer, text, integer) from public, anon, authenticated;
revoke all on function public.get_reservation(bigint, bigint) from public, anon, authenticated;
revoke all on function public.confirm_reservation(bigint, bigint) from public, anon, authenticated;
revoke all on function public.fail_payment(bigint, bigint) from public, anon, authenticated;
revoke all on function public.cancel_reservation(bigint, bigint) from public, anon, authenticated;
revoke all on function public.booking_history(bigint) from public, anon, authenticated;
revoke all on function public.cleanup_expired_reservations() from public, anon, authenticated;

grant execute on function public.list_seats(boolean) to service_role;
grant execute on function public.reserve_seat(bigint, integer, text, integer) to service_role;
grant execute on function public.get_reservation(bigint, bigint) to service_role;
grant execute on function public.confirm_reservation(bigint, bigint) to service_role;
grant execute on function public.fail_payment(bigint, bigint) to service_role;
grant execute on function public.cancel_reservation(bigint, bigint) to service_role;
grant execute on function public.booking_history(bigint) to service_role;
grant execute on function public.cleanup_expired_reservations() to service_role;
