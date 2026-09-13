-- ============================================================================
-- FinGuru 2.0 — Preferred currency + AI persona columns
-- Adds two per-user settings columns to the existing `profiles` table:
--
--   preferred_currency — the currency the user wants all money shown in
--     (INR, USD, EUR, GBP, JPY, AUD, CAD, SGD, AED, CHF). Stored amounts stay
--     in INR; the app converts at the display/AI boundary using a live FX
--     rate. Default 'INR' preserves today's behaviour for existing users.
--
--   risk_tolerance — the user's Investment Risk Tolerance for AI personalization
--     (Very Conservative, Moderate, Aggressive, Wall Street Bets). Default
--     'Moderate'.
--
-- HOW TO RUN: Open the Supabase Dashboard → SQL Editor → paste & *Run*.
-- Run AFTER migrations/001 (it depends on the `profiles` table).
-- Idempotent: safe to re-run (each ALTER guards with IF NOT EXISTS).
-- ============================================================================

alter table public.profiles
    add column if not exists preferred_currency text not null default 'INR';

alter table public.profiles
    add column if not exists risk_tolerance      text not null default 'Moderate';