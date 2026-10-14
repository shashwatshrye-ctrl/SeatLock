create table if not exists public.seats (
    id integer primary key check (id between 1 and 500),
    label text not null unique
);

insert into public.seats (id, label)
select generated.n, 'Seat ' || lpad(generated.n::text, 3, '0')
from generate_series(1, 500) as generated(n)
on conflict (id) do nothing;

create table if not exists public.reservations (
    id uuid primary key default gen_random_uuid(),
    seat_id integer not null references public.seats(id),
    user_id uuid not null,
    idempotency_key text not null check (length(idempotency_key) between 1 and 128),
    status text not null check (
        status in ('reserved', 'confirmed', 'cancelled', 'expired', 'payment_failed')
    ),
    created_at timestamptz not null default now(),
    expires_at timestamptz,
    confirmed_at timestamptz,
    unique (user_id, idempotency_key)
);

create unique index if not exists one_live_booking_per_seat
on public.reservations (seat_id)
where status in ('reserved', 'confirmed');

create index if not exists reservations_by_user
on public.reservations (user_id, created_at desc);

create or replace function public.list_seats(p_available_only boolean default false)
returns jsonb
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select coalesce(jsonb_agg(jsonb_build_object(
        'id', s.id,
        'label', s.label,
        'available', not exists (
            select 1
            from public.reservations r
            where r.seat_id = s.id
              and (
                  r.status = 'confirmed'
                  or (r.status = 'reserved' and r.expires_at > now())
              )
        )
    ) order by s.id), '[]'::jsonb)
    from public.seats s
    where not p_available_only or not exists (
        select 1
        from public.reservations r
        where r.seat_id = s.id
          and (
              r.status = 'confirmed'
              or (r.status = 'reserved' and r.expires_at > now())
          )
    );
$$;

create or replace function public.reserve_seat(
    p_user_id uuid,
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

    perform pg_advisory_xact_lock(hashtextextended(p_user_id::text || ':' || p_idempotency_key, 0));

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

    perform 1 from public.seats where id = p_seat_id for update;
    if not found then
        return jsonb_build_object('error', 'seat_not_found');
    end if;

    update public.reservations
    set status = 'expired'
    where seat_id = p_seat_id
      and status = 'reserved'
      and expires_at <= clock_timestamp();

    if exists (
        select 1 from public.reservations
        where seat_id = p_seat_id
          and (status = 'confirmed' or (status = 'reserved' and expires_at > clock_timestamp()))
    ) then
        return jsonb_build_object('error', 'seat_unavailable');
    end if;

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

create or replace function public.get_reservation(p_reservation_id uuid, p_user_id uuid)
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
    where id = p_reservation_id and user_id = p_user_id;

    if not found then
        return jsonb_build_object('error', 'reservation_not_found');
    end if;

    if v_reservation.status = 'reserved' and v_reservation.expires_at <= now() then
        return to_jsonb(v_reservation) || jsonb_build_object('status', 'expired');
    end if;

    return to_jsonb(v_reservation);
end;
$$;

create or replace function public.confirm_reservation(p_reservation_id uuid, p_user_id uuid)
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

create or replace function public.fail_payment(p_reservation_id uuid, p_user_id uuid)
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

create or replace function public.cancel_reservation(p_reservation_id uuid, p_user_id uuid)
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

create or replace function public.booking_history(p_user_id uuid)
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

alter table public.seats enable row level security;
alter table public.reservations enable row level security;
revoke all on table public.seats, public.reservations from anon, authenticated;

revoke all on function public.list_seats(boolean) from public, anon, authenticated;
revoke all on function public.reserve_seat(uuid, integer, text, integer) from public, anon, authenticated;
revoke all on function public.get_reservation(uuid, uuid) from public, anon, authenticated;
revoke all on function public.confirm_reservation(uuid, uuid) from public, anon, authenticated;
revoke all on function public.fail_payment(uuid, uuid) from public, anon, authenticated;
revoke all on function public.cancel_reservation(uuid, uuid) from public, anon, authenticated;
revoke all on function public.booking_history(uuid) from public, anon, authenticated;

grant execute on function public.list_seats(boolean) to service_role;
grant execute on function public.reserve_seat(uuid, integer, text, integer) to service_role;
grant execute on function public.get_reservation(uuid, uuid) to service_role;
grant execute on function public.confirm_reservation(uuid, uuid) to service_role;
grant execute on function public.fail_payment(uuid, uuid) to service_role;
grant execute on function public.cancel_reservation(uuid, uuid) to service_role;
grant execute on function public.booking_history(uuid) to service_role;
