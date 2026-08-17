-- =====================================================================
-- QuickCart — Core Schema (Migration 0001)
-- Target: Supabase Postgres
-- Notes:
--   * auth.users (Supabase Auth) is the source of truth for login/JWT.
--     `customers` and `retailers` are 1:1 profile tables keyed on auth.users.id.
--   * All monetary values stored in the smallest currency unit (paise) as
--     BIGINT to avoid floating point rounding errors. Convert to INR in the API layer.
--   * Every table has RLS enabled. Policies are defined per-role at the bottom.
-- =====================================================================

create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- ENUM TYPES
-- ---------------------------------------------------------------------
create type user_role as enum ('customer', 'retailer', 'employee', 'admin');
create type store_type as enum ('grocery', 'hypermarket', 'mini_mart');
create type session_status as enum ('active', 'checked_out', 'abandoned', 'blocked_exit');
create type payment_status as enum ('pending', 'success', 'failed', 'refunded');
create type exit_status as enum ('not_exited', 'exited', 'blocked');
create type alert_severity as enum ('low', 'medium', 'high', 'critical');
create type alert_status as enum ('open', 'acknowledged', 'resolved', 'false_positive');
create type camera_status as enum ('online', 'offline', 'error');

-- ---------------------------------------------------------------------
-- CUSTOMERS  (1:1 with auth.users)
-- ---------------------------------------------------------------------
create table customers (
    id              uuid primary key references auth.users(id) on delete cascade,
    full_name       text not null,
    phone           text unique,
    avatar_url      text,
    wishlist        uuid[] default '{}',        -- array of product ids
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- RETAILERS  (1:1 with auth.users) — owns one or more stores
-- ---------------------------------------------------------------------
create table retailers (
    id              uuid primary key references auth.users(id) on delete cascade,
    business_name   text not null,
    gstin           text,
    phone           text unique,
    verified        boolean not null default false,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- EMPLOYEE ACCOUNTS — retailer staff who can operate the exit-scan device
-- ---------------------------------------------------------------------
create table employee_accounts (
    id              uuid primary key default gen_random_uuid(),
    retailer_id     uuid not null references retailers(id) on delete cascade,
    auth_user_id    uuid references auth.users(id) on delete set null,
    full_name       text not null,
    role            text not null default 'checkout_staff', -- checkout_staff | manager
    active          boolean not null default true,
    created_at      timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- STORES
-- ---------------------------------------------------------------------
create table stores (
    id              uuid primary key default gen_random_uuid(),
    retailer_id     uuid not null references retailers(id) on delete cascade,
    name            text not null,
    store_type      store_type not null,
    image_url       text,
    address_line    text,
    city            text,
    state           text,
    pincode         text,
    latitude        double precision,
    longitude       double precision,
    opening_time    time,
    closing_time    time,
    rating          numeric(2,1) default 0.0,
    is_active       boolean not null default true,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
create index idx_stores_retailer on stores(retailer_id);
create index idx_stores_location on stores(latitude, longitude);

-- ---------------------------------------------------------------------
-- CATEGORIES
-- ---------------------------------------------------------------------
create table categories (
    id              uuid primary key default gen_random_uuid(),
    store_id        uuid not null references stores(id) on delete cascade,
    name            text not null,
    parent_id       uuid references categories(id) on delete set null,
    created_at      timestamptz not null default now(),
    unique (store_id, name)
);

-- ---------------------------------------------------------------------
-- PRODUCTS
-- ---------------------------------------------------------------------
create table products (
    id                  uuid primary key default gen_random_uuid(),
    store_id            uuid not null references stores(id) on delete cascade,
    category_id         uuid references categories(id) on delete set null,
    barcode             text not null,
    name                text not null,
    brand               text,
    description         text,
    image_url           text,
    mrp_paise           bigint not null check (mrp_paise >= 0),
    discount_percent    numeric(5,2) not null default 0 check (discount_percent >= 0 and discount_percent <= 100),
    price_paise         bigint generated always as (
        round(mrp_paise * (1 - discount_percent / 100.0))
    ) stored,
    gst_percent         numeric(5,2) not null default 0,
    weight_value         numeric(10,2),
    weight_unit          text,                 -- g, kg, ml, l, pcs
    manufacture_date    date,
    expiry_date         date,
    stock_quantity      integer not null default 0 check (stock_quantity >= 0),
    low_stock_threshold integer not null default 5,
    supplier_name       text,
    supplier_contact    text,
    shelf_location      text,                 -- e.g. "Aisle 3, Rack B" — used by AI to map camera zones to products
    is_active           boolean not null default true,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    unique (store_id, barcode)
);
create index idx_products_store on products(store_id);
create index idx_products_barcode on products(store_id, barcode);
create index idx_products_low_stock on products(store_id) where stock_quantity <= low_stock_threshold;

-- ---------------------------------------------------------------------
-- SHOPPING SESSIONS — one per customer visit to a store
-- ---------------------------------------------------------------------
create table shopping_sessions (
    id                  uuid primary key default gen_random_uuid(),
    customer_id         uuid not null references customers(id) on delete cascade,
    store_id            uuid not null references stores(id) on delete cascade,
    status              session_status not null default 'active',
    payment_status      payment_status not null default 'pending',
    exit_status         exit_status not null default 'not_exited',
    entry_time          timestamptz not null default now(),
    checkout_time       timestamptz,
    exit_time           timestamptz,
    qr_pass_token       text,           -- encrypted payload, set after successful payment
    qr_pass_expires_at  timestamptz,
    created_at          timestamptz not null default now()
);
create index idx_sessions_customer on shopping_sessions(customer_id);
create index idx_sessions_store_active on shopping_sessions(store_id) where status = 'active';

-- ---------------------------------------------------------------------
-- CART ITEMS — barcode-scanned items within a session
-- ---------------------------------------------------------------------
create table cart_items (
    id              uuid primary key default gen_random_uuid(),
    session_id      uuid not null references shopping_sessions(id) on delete cascade,
    product_id      uuid not null references products(id),
    quantity        integer not null default 1 check (quantity > 0),
    unit_price_paise bigint not null,  -- snapshot of price at scan time
    scanned_at      timestamptz not null default now(),
    removed_at      timestamptz        -- soft delete when customer removes from cart
);
create index idx_cart_items_session on cart_items(session_id);

-- ---------------------------------------------------------------------
-- PAYMENTS
-- ---------------------------------------------------------------------
create table payments (
    id                  uuid primary key default gen_random_uuid(),
    session_id          uuid not null references shopping_sessions(id) on delete cascade,
    provider            text not null default 'razorpay',
    provider_order_id   text,
    provider_payment_id text,
    method              text,           -- upi | card | netbanking | wallet
    amount_paise        bigint not null,
    status              payment_status not null default 'pending',
    failure_reason      text,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);
create index idx_payments_session on payments(session_id);

-- ---------------------------------------------------------------------
-- INVOICES
-- ---------------------------------------------------------------------
create table invoices (
    id                  uuid primary key default gen_random_uuid(),
    session_id          uuid not null references shopping_sessions(id) on delete cascade,
    payment_id          uuid references payments(id),
    invoice_number      text not null unique,
    subtotal_paise      bigint not null,
    discount_paise      bigint not null default 0,
    gst_paise           bigint not null default 0,
    total_paise         bigint not null,
    pdf_storage_path    text,           -- Supabase Storage path
    emailed             boolean not null default false,
    created_at          timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- CCTV CAMERAS
-- ---------------------------------------------------------------------
create table cctv_cameras (
    id              uuid primary key default gen_random_uuid(),
    store_id        uuid not null references stores(id) on delete cascade,
    label           text not null,          -- "Aisle 1 - North"
    stream_url      text not null,          -- RTSP/HLS endpoint, never exposed to customer clients
    covers_shelf_locations text[],          -- maps to products.shelf_location for cart-vs-shelf checks
    status          camera_status not null default 'offline',
    last_heartbeat  timestamptz,
    created_at      timestamptz not null default now()
);
create index idx_cameras_store on cctv_cameras(store_id);

-- ---------------------------------------------------------------------
-- AI ALERTS
-- ---------------------------------------------------------------------
create table ai_alerts (
    id                  uuid primary key default gen_random_uuid(),
    session_id          uuid references shopping_sessions(id) on delete cascade,
    store_id            uuid not null references stores(id) on delete cascade,
    camera_id           uuid references cctv_cameras(id),
    severity            alert_severity not null,
    status              alert_status not null default 'open',
    reason              text not null,          -- e.g. "cart_scan_mismatch", "concealment_gesture", "shelf_mismatch"
    confidence_score    numeric(5,2),
    snapshot_storage_path text,
    clip_storage_path   text,
    detected_at         timestamptz not null default now(),
    resolved_at         timestamptz,
    resolved_by         uuid references retailers(id)
);
create index idx_alerts_store_open on ai_alerts(store_id) where status = 'open';
create index idx_alerts_session on ai_alerts(session_id);

-- ---------------------------------------------------------------------
-- NOTIFICATIONS (generic, drives both retailer + customer notification feeds)
-- ---------------------------------------------------------------------
create table notifications (
    id              uuid primary key default gen_random_uuid(),
    recipient_type  user_role not null,
    recipient_id    uuid not null,          -- customers.id or retailers.id
    title           text not null,
    body            text,
    category        text not null,          -- low_stock | out_of_stock | payment | ai_alert | system
    related_id      uuid,                   -- e.g. ai_alerts.id, payments.id
    read_at         timestamptz,
    created_at      timestamptz not null default now()
);
create index idx_notifications_recipient on notifications(recipient_type, recipient_id, read_at);

-- ---------------------------------------------------------------------
-- LOGS / ACTIVITY HISTORY (append-only audit trail)
-- ---------------------------------------------------------------------
create table activity_logs (
    id              uuid primary key default gen_random_uuid(),
    actor_role       user_role,
    actor_id        uuid,
    action          text not null,          -- e.g. "product.update", "session.checkout"
    entity_type     text,
    entity_id       uuid,
    metadata        jsonb default '{}',
    created_at      timestamptz not null default now()
);
create index idx_logs_entity on activity_logs(entity_type, entity_id);

-- =====================================================================
-- updated_at trigger helper
-- =====================================================================
create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger trg_customers_updated_at before update on customers
    for each row execute function set_updated_at();
create trigger trg_retailers_updated_at before update on retailers
    for each row execute function set_updated_at();
create trigger trg_stores_updated_at before update on stores
    for each row execute function set_updated_at();
create trigger trg_products_updated_at before update on products
    for each row execute function set_updated_at();
create trigger trg_payments_updated_at before update on payments
    for each row execute function set_updated_at();

-- =====================================================================
-- ROW LEVEL SECURITY
-- =====================================================================
alter table customers enable row level security;
alter table retailers enable row level security;
alter table employee_accounts enable row level security;
alter table stores enable row level security;
alter table categories enable row level security;
alter table products enable row level security;
alter table shopping_sessions enable row level security;
alter table cart_items enable row level security;
alter table payments enable row level security;
alter table invoices enable row level security;
alter table cctv_cameras enable row level security;
alter table ai_alerts enable row level security;
alter table notifications enable row level security;
alter table activity_logs enable row level security;

-- Customers can read/update only their own profile
create policy "customers_self_select" on customers for select using (auth.uid() = id);
create policy "customers_self_update" on customers for update using (auth.uid() = id);

-- Retailers can read/update only their own profile
create policy "retailers_self_select" on retailers for select using (auth.uid() = id);
create policy "retailers_self_update" on retailers for update using (auth.uid() = id);

-- Stores: publicly readable (customers browsing nearby stores), writable only by owning retailer
create policy "stores_public_select" on stores for select using (is_active = true);
create policy "stores_owner_all" on stores for all using (auth.uid() = retailer_id);

-- Products: publicly readable per active store, writable only by owning retailer
create policy "products_public_select" on products for select using (is_active = true);
create policy "products_owner_all" on products for all using (
    auth.uid() = (select retailer_id from stores where stores.id = products.store_id)
);

-- Categories follow the same ownership pattern as products
create policy "categories_public_select" on categories for select using (true);
create policy "categories_owner_all" on categories for all using (
    auth.uid() = (select retailer_id from stores where stores.id = categories.store_id)
);

-- Shopping sessions: a customer sees only their own sessions;
-- the owning retailer sees sessions that belong to their store.
create policy "sessions_customer_select" on shopping_sessions for select using (auth.uid() = customer_id);
create policy "sessions_customer_insert" on shopping_sessions for insert with check (auth.uid() = customer_id);
create policy "sessions_retailer_select" on shopping_sessions for select using (
    auth.uid() = (select retailer_id from stores where stores.id = shopping_sessions.store_id)
);

-- Cart items: visible to the session's customer and the store's retailer
create policy "cart_items_customer_all" on cart_items for all using (
    auth.uid() = (select customer_id from shopping_sessions where shopping_sessions.id = cart_items.session_id)
);
create policy "cart_items_retailer_select" on cart_items for select using (
    auth.uid() = (
        select s.retailer_id from shopping_sessions ss
        join stores s on s.id = ss.store_id
        where ss.id = cart_items.session_id
    )
);

-- Payments / invoices: same pattern as cart_items
create policy "payments_customer_select" on payments for select using (
    auth.uid() = (select customer_id from shopping_sessions where shopping_sessions.id = payments.session_id)
);
create policy "invoices_customer_select" on invoices for select using (
    auth.uid() = (select customer_id from shopping_sessions where shopping_sessions.id = invoices.session_id)
);

-- CCTV cameras: retailer-only, never exposed to customers
create policy "cameras_owner_all" on cctv_cameras for all using (
    auth.uid() = (select retailer_id from stores where stores.id = cctv_cameras.store_id)
);

-- AI alerts: retailer-only
create policy "alerts_owner_all" on ai_alerts for all using (
    auth.uid() = (select retailer_id from stores where stores.id = ai_alerts.store_id)
);

-- Notifications: each recipient sees only their own
create policy "notifications_self_select" on notifications for select using (
    recipient_id = auth.uid()
);

-- Activity logs: service-role only (written by backend, not exposed to clients directly)
create policy "activity_logs_service_only" on activity_logs for all using (false);

-- NOTE: The backend uses the Supabase *service role* key for privileged operations
-- (creating sessions on behalf of validated requests, writing AI alerts, generating
-- invoices, etc.). The service role bypasses RLS by design — RLS above protects
-- direct client access via the anon/public key.
