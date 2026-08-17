-- =====================================================================
-- QuickCart — Storage buckets (Migration 0002)
-- =====================================================================

-- Invoice PDFs. Private by default — access is granted only through the
-- backend's service-role client (invoice_service.py) or short-lived signed
-- URLs, never direct public bucket listing, since invoices contain a
-- customer's purchase history.
insert into storage.buckets (id, name, public)
values ('invoices', 'invoices', false)
on conflict (id) do nothing;

-- Customers may read only their own invoice PDFs; matching is done by
-- invoice_number prefix since object paths are named "<invoice_number>.pdf"
-- and invoice_number embeds no customer-identifying info directly — this
-- policy instead joins through invoices -> shopping_sessions -> customer_id.
create policy "invoice_pdfs_owner_read"
on storage.objects for select
using (
    bucket_id = 'invoices'
    and auth.uid() = (
        select ss.customer_id
        from invoices i
        join shopping_sessions ss on ss.id = i.session_id
        where i.pdf_storage_path = storage.objects.name
    )
);

-- Product images, store images, camera snapshots/clips for AI alerts (used from Phase 5-6 onward).
insert into storage.buckets (id, name, public)
values ('product-images', 'product-images', true)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('store-images', 'store-images', true)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('ai-alert-media', 'ai-alert-media', false)
on conflict (id) do nothing;

create policy "ai_alert_media_owner_read"
on storage.objects for select
using (
    bucket_id = 'ai-alert-media'
    and auth.uid() = (
        select s.retailer_id
        from ai_alerts a
        join stores s on s.id = a.store_id
        where a.snapshot_storage_path = storage.objects.name
           or a.clip_storage_path = storage.objects.name
    )
);
