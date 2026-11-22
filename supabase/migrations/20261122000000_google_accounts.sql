begin;

create table public.yourspace_users (
    id text primary key default gen_random_uuid()::text,
    google_sub text not null unique,
    email text not null,
    name text not null,
    location text not null default '',
    home_type text not null default 'apartment',
    preferred_units text not null default 'ft',
    created_at timestamptz not null default now()
);

create table public.yourspace_sessions (
    token_hash text primary key,
    user_id text not null references public.yourspace_users(id) on delete cascade,
    expires_at timestamptz not null
);

alter table public.yourspace_users enable row level security;
alter table public.yourspace_sessions enable row level security;
revoke all on public.yourspace_users, public.yourspace_sessions from public, anon, authenticated;
grant select, insert, update on public.yourspace_users to service_role;
grant select, insert, delete on public.yourspace_sessions to service_role;

create function public.yourspace_sign_in_google(
    subject text, verified_email text, display_name text, previous_profile jsonb
)
returns setof public.yourspace_users
language sql
set search_path = ''
as $$
    insert into public.yourspace_users (
        id, google_sub, email, name, location, home_type, preferred_units
    ) values (
        coalesce(previous_profile->>'id', gen_random_uuid()::text),
        subject, verified_email, coalesce(previous_profile->>'name', display_name),
        coalesce(previous_profile->>'location', ''),
        coalesce(previous_profile->>'home_type', 'apartment'),
        coalesce(previous_profile->>'preferred_units', 'ft')
    )
    on conflict (google_sub) do update set email = excluded.email
    returning *;
$$;

revoke all on function public.yourspace_sign_in_google(text, text, text, jsonb)
    from public, anon, authenticated;
grant execute on function public.yourspace_sign_in_google(text, text, text, jsonb)
    to service_role;

commit;
