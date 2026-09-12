-- ============================================================================
-- FinGuru 2.0 — Final-Year Major Project schema
-- New modules: Income Tax, Portfolio, Net Worth, FIRE, AI CA Chatbot
--
-- HOW TO RUN: Open the Supabase Dashboard → SQL Editor → paste & *Run*.
-- All tables are scoped per user with Row Level Security: a user can only
-- read/write their own rows. `auth.uid()` is the logged-in Supabase user id.
--
-- Idempotent: safe to re-run (each block guards with IF NOT EXISTS).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. TAX PROFILE — a user's saved tax declaration for a financial year
-- ----------------------------------------------------------------------------
create table if not exists public.tax_profiles (
    id                 uuid primary key default gen_random_uuid(),
    user_id            uuid not null references auth.users(id) on delete cascade,
    financial_year     text not null default '2026-27',   -- AY, e.g. 2026-27
    age                int  not null default 30,
    residential_status text not null default 'Resident',
    -- Income heads (gross annual, INR)
    income             jsonb not null default '{"salary":0,"bonus":0,"interest_income":0,"rental_income":0,"ltcg":0,"stcg":0,"other_income":0}',
    -- Deductions / exemptions for the old regime
    deductions         jsonb not null default '{"sec_80c":0,"sec_80d_self":0,"sec_80d_parents":0,"sec_80ccd_1b":0,"sec_80g":0,"nps_employer":0,"home_loan_interest":0,"hra_basic_salary":0,"hra_received":0,"hra_rent_paid":0,"hra_is_metro":false}',
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now(),
    unique (user_id, financial_year)
);

-- ----------------------------------------------------------------------------
-- 2. TAX CALCULATIONS — computed results (history + chatbot grounding source)
-- ----------------------------------------------------------------------------
create table if not exists public.tax_calculations (
    id                 uuid primary key default gen_random_uuid(),
    user_id            uuid not null references auth.users(id) on delete cascade,
    financial_year     text not null default '2026-27',
    old_regime_tax     numeric not null default 0,
    new_regime_tax     numeric not null default 0,
    recommended_regime text not null default '',
    potential_saving   numeric not null default 0,
    breakdown          jsonb not null default '{}',   -- full line-item dict
    created_at         timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- 3. INVESTMENTS — stocks / mutual funds / FDs / gold / property (manual)
-- ----------------------------------------------------------------------------
create table if not exists public.investments (
    id             uuid primary key default gen_random_uuid(),
    user_id        uuid not null references auth.users(id) on delete cascade,
    asset_type     text not null default 'Mutual Fund', -- Stock|Mutual Fund|FD|Gold|Property|Other
    name           text not null,
    invested_amount numeric not null default 0,
    current_value  numeric not null default 0,
    -- Stock
    quantity       numeric,
    buy_price      numeric,
    current_price  numeric,
    -- Mutual Fund
    units          numeric,
    purchase_nav   numeric,
    current_nav    numeric,
    -- FD
    principal      numeric,
    interest_rate  numeric,
    start_date     date,
    maturity_date  date,
    -- Common
    purchased_on   date,
    notes          text,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- 4. LIABILITIES — debts (home/education/car/credit card/personal/other)
-- ----------------------------------------------------------------------------
create table if not exists public.liabilities (
    id                 uuid primary key default gen_random_uuid(),
    user_id            uuid not null references auth.users(id) on delete cascade,
    liability_type     text not null default 'Other', -- Home|Education|Car|Credit Card|Personal|Other
    name               text not null,
    outstanding_amount numeric not null default 0,
    interest_rate      numeric not null default 0,
    start_date         date,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- 5. NET WORTH SNAPSHOTS — one per calendar month → growth chart
-- ----------------------------------------------------------------------------
create table if not exists public.net_worth_snapshots (
    id               uuid primary key default gen_random_uuid(),
    user_id          uuid not null references auth.users(id) on delete cascade,
    snapshot_date    date not null default current_date,
    total_assets     numeric not null default 0,
    total_liabilities numeric not null default 0,
    net_worth        numeric not null default 0,
    breakdown        jsonb not null default '{}',
    created_at       timestamptz not null default now(),
    unique (user_id, snapshot_date)
);

-- ----------------------------------------------------------------------------
-- 6. FIRE PROFILES — one row per user's retirement plan
-- ----------------------------------------------------------------------------
create table if not exists public.fire_profiles (
    id                     uuid primary key default gen_random_uuid(),
    user_id                uuid not null references auth.users(id) on delete cascade,
    current_age            int  not null default 22,
    target_retirement_age  int  not null default 45,
    monthly_expense        numeric not null default 30000,
    monthly_investment     numeric not null default 20000,
    current_corpus         numeric not null default 0,
    expected_return_pct    numeric not null default 10,
    inflation_pct          numeric not null default 6,
    safe_withdrawal_rate_pct numeric not null default 4,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now(),
    unique (user_id)
);

-- ----------------------------------------------------------------------------
-- 7. FIRE SIMULATIONS — Monte Carlo run history
-- ----------------------------------------------------------------------------
create table if not exists public.fire_simulations (
    id                uuid primary key default gen_random_uuid(),
    user_id           uuid not null references auth.users(id) on delete cascade,
    fire_profile_id   uuid references public.fire_profiles(id) on delete set null,
    target_age        int  not null,
    required_corpus   numeric not null default 0,
    projected_corpus  numeric not null default 0,   -- median terminal corpus
    probability_pct   numeric not null default 0,
    p5                numeric not null default 0,
    p95               numeric not null default 0,
    simulations_count int  not null default 3000,
    created_at        timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- 8. AI CONVERSATIONS — audit trail for the CA chatbot
-- ----------------------------------------------------------------------------
create table if not exists public.ai_conversations (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    user_message text not null,
    context     jsonb not null default '{}',   -- grounding data sent to Gemini
    ai_response text not null default '',
    model       text not null default '',
    created_at  timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- ROW LEVEL SECURITY
-- ----------------------------------------------------------------------------
alter table public.tax_profiles         enable row level security;
alter table public.tax_calculations     enable row level security;
alter table public.investments          enable row level security;
alter table public.liabilities          enable row level security;
alter table public.net_worth_snapshots  enable row level security;
alter table public.fire_profiles        enable row level security;
alter table public.fire_simulations     enable row level security;
alter table public.ai_conversations     enable row level security;

do $$
declare t text;
begin
    foreach t in array array[
        'tax_profiles','tax_calculations','investments','liabilities',
        'net_worth_snapshots','fire_profiles','fire_simulations','ai_conversations'
    ] loop
        execute format('create policy "Users can view own rows" on public.%I for select using (auth.uid() = user_id)', t);
        execute format('create policy "Users can insert own rows" on public.%I for insert with check (auth.uid() = user_id)', t);
        execute format('create policy "Users can update own rows" on public.%I for update using (auth.uid() = user_id)', t);
        execute format('create policy "Users can delete own rows" on public.%I for delete using (auth.uid() = user_id)', t);
    end loop;
end $$;

-- ----------------------------------------------------------------------------
-- Indexes for common lookups
-- ----------------------------------------------------------------------------
create index if not exists idx_tax_profile_user        on public.tax_profiles(user_id);
create index if not exists idx_tax_calc_user_fy        on public.tax_calculations(user_id, financial_year);
create index if not exists idx_investments_user        on public.investments(user_id);
create index if not exists idx_liabilities_user        on public.liabilities(user_id);
create index if not exists idx_nw_snapshot_user_date   on public.net_worth_snapshots(user_id, snapshot_date);
create index if not exists idx_fire_sim_user           on public.fire_simulations(user_id);
create index if not exists idx_ai_convs_user           on public.ai_conversations(user_id, created_at);