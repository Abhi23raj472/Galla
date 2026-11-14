-- Galla: one private ledger row per signed-in user.
-- Run this once in Supabase: Dashboard -> SQL Editor -> New query -> paste -> Run.

create table if not exists public.ledgers (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  data       jsonb not null,
  version    bigint not null default 1,
  updated_at timestamptz not null default now(),
  constraint ledger_size check (octet_length(data::text) < 5000000)
);

alter table public.ledgers enable row level security;

-- Each user can only see and change their own row.
drop policy if exists "Users read their own ledger" on public.ledgers;
create policy "Users read their own ledger" on public.ledgers
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "Users create their own ledger" on public.ledgers;
create policy "Users create their own ledger" on public.ledgers
  for insert to authenticated with check ((select auth.uid()) = user_id);

drop policy if exists "Users update their own ledger" on public.ledgers;
create policy "Users update their own ledger" on public.ledgers
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

drop policy if exists "Users delete their own ledger" on public.ledgers;
create policy "Users delete their own ledger" on public.ledgers
  for delete to authenticated using ((select auth.uid()) = user_id);
