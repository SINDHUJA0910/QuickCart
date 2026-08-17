-- =====================================================================
-- QuickCart — Hardening (Migration 0005)
-- Closes two gaps explicitly flagged as known limitations in earlier
-- phases rather than left as silent debt.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Atomic stock adjustment (flagged in Phase 3's cart_service.py docstring)
-- ---------------------------------------------------------------------
-- Previously: application code did SELECT stock_quantity, compute new
-- value in Python, then UPDATE — two round trips with a race window under
-- concurrent scans of the same product. This function does the increment
-- and the floor check in one atomic UPDATE statement, so Postgres's own
-- row-level locking serializes concurrent callers correctly.
create or replace function adjust_product_stock(p_product_id uuid, p_delta int)
returns products
language plpgsql
as $$
declare
    updated products;
begin
    update products
       set stock_quantity = stock_quantity + p_delta
     where id = p_product_id
       and stock_quantity + p_delta >= 0
    returning * into updated;

    if not found then
        raise exception 'insufficient_stock' using errcode = 'P0001';
    end if;

    return updated;
end;
$$;

-- ---------------------------------------------------------------------
-- 2. DB-level enforcement of "one active session per customer"
-- ---------------------------------------------------------------------
-- Previously enforced only in application code (session_service.py:
-- query-then-insert). That's the authoritative business-rule check (it
-- returns a friendly 409 with a clear message), but it has the same
-- race-condition shape as #1 above under concurrent requests. This
-- partial unique index is the safety net: even if two requests race past
-- the application check simultaneously, Postgres itself will reject the
-- second insert. The application-level check remains in place because it
-- produces a much better error message than a raw constraint violation.
create unique index if not exists uq_one_active_session_per_customer
    on shopping_sessions (customer_id)
    where status = 'active';
