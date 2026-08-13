create extension if not exists "pgcrypto";

-- Investify Analytics v51 option contract tracking table.
-- Run this once in Supabase SQL Editor before deploying v51 cloud options sync.

create table if not exists public.option_positions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  portfolio_id uuid references public.portfolios(id) on delete cascade,
  strategy text not null default 'single',
  spread_type text,
  underlying text not null,
  option_type text not null default 'call',
  position_side text not null default 'long',
  expiration date not null,
  strike numeric,
  short_strike numeric,
  long_strike numeric,
  contracts numeric not null default 1,
  entry_price numeric not null default 0,
  account text default 'Brokerage',
  notes text,
  opened_at date default current_date,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.option_positions enable row level security;

drop policy if exists "option positions own rows" on public.option_positions;

create policy "option positions own rows"
on public.option_positions
for all
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create index if not exists option_positions_user_portfolio_idx
on public.option_positions(user_id, portfolio_id, created_at desc);
