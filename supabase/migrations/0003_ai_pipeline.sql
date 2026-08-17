-- =====================================================================
-- QuickCart — AI pipeline support (Migration 0003)
-- =====================================================================

-- Pixel-coordinate ROI configuration per camera, operator-defined at
-- camera setup time. Each entry: {"zone_id": str, "x1","y1","x2","y2": int,
-- "shelf_location": str (matches products.shelf_location for reporting)}.
alter table cctv_cameras
    add column if not exists zone_config jsonb not null default '[]';

-- Persisted output of theft_logic/shelf_activity.py's frame-differencing —
-- one row per detected "something changed on this shelf" event. This is
-- the raw signal the mismatch engine correlates against scanned cart items;
-- kept as its own append-only table (rather than folding into ai_alerts)
-- since most shelf events are completely normal shopping activity, not
-- alerts — only a sustained mismatch between this table and cart_items
-- becomes an ai_alerts row.
create table shelf_events (
    id                  uuid primary key default gen_random_uuid(),
    camera_id           uuid not null references cctv_cameras(id) on delete cascade,
    store_id            uuid not null references stores(id) on delete cascade,
    zone_id             text not null,
    changed_area_ratio  numeric(6,4) not null,
    detected_at         timestamptz not null default now()
);
create index idx_shelf_events_store_time on shelf_events(store_id, detected_at);

alter table shelf_events enable row level security;
create policy "shelf_events_owner_all" on shelf_events for all using (
    auth.uid() = (select retailer_id from stores where stores.id = shelf_events.store_id)
);
