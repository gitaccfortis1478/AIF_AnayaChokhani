begin;

create table public.yourspace_projects (
    project_id text primary key,
    project_name text not null check (btrim(project_name) <> ''),
    user_id text not null references public.yourspace_users(id),
    draft_progress jsonb not null default '{}'::jsonb
        check (jsonb_typeof(draft_progress) = 'object'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.yourspace_designs (
    design_id text primary key,
    project_id text not null references public.yourspace_projects(project_id) on delete cascade,
    session_id text,
    total_price_inr bigint not null default 0 check (total_price_inr >= 0),
    item_count integer not null default 0 check (item_count >= 0),
    room_type text not null,
    style_words text[] not null default '{}'::text[],
    image_data_url text,
    status text not null check (status in ('failed', 'passed')),
    generated_at timestamptz not null default now(),
    design_data jsonb not null default '{}'::jsonb
        check (jsonb_typeof(design_data) = 'object')
);

comment on column public.yourspace_projects.draft_progress is
    'Wizard step and editable form values. Store image references here when object storage is available.';
comment on column public.yourspace_designs.session_id is
    'Optional reference to the planner session. This is separate from the login session.';
comment on column public.yourspace_designs.image_data_url is
    'Reserved for future image integration. Leave null for now.';
comment on column public.yourspace_designs.design_data is
    'Room brief, selected items, validation results, and revision metadata for reopening the design. Excludes image bytes.';

create index yourspace_projects_owner_updated_idx
    on public.yourspace_projects (user_id, updated_at desc);
create index yourspace_designs_project_generated_idx
    on public.yourspace_designs (project_id, generated_at desc);

create function public.yourspace_touch_project_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

revoke all on function public.yourspace_touch_project_updated_at()
    from public, anon, authenticated;

create trigger yourspace_projects_touch_updated_at
before update on public.yourspace_projects
for each row execute function public.yourspace_touch_project_updated_at();

alter table public.yourspace_projects enable row level security;
alter table public.yourspace_designs enable row level security;
revoke all on public.yourspace_projects, public.yourspace_designs
    from public, anon, authenticated;
grant select, insert, update, delete on public.yourspace_projects, public.yourspace_designs
    to service_role;

commit;
