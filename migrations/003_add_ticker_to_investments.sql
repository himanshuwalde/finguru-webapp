-- ============================================================================
-- FinGuru 2.0 — Live portfolio pricing: ticker column
-- Adds an optional `ticker` column to the existing `investments` table.
--
--   ticker — the Yahoo Finance symbol used to fetch the LIVE market price on
--     portfolio reads (e.g. RELIANCE.NS for NSE, HDFCBANK.BO for BSE). Stocks
--     and direct equity mutual funds have live coverage; FD / Gold / Property /
--     Other and un-listed schemes stay manual. When a ticker resolves we overlay
--     the live price at read time — the stored current_price / current_nav stays
--     untouched as the manual fallback, and a bad/offline ticker silently falls
--     back to it.
--
-- HOW TO RUN: Open the Supabase Dashboard → SQL Editor → paste & *Run*.
-- Run AFTER migrations/001 (it depends on the `investments` table).
-- Idempotent: safe to re-run (guarded with IF NOT EXISTS).
-- ============================================================================

alter table public.investments
    add column if not exists ticker text;