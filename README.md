# QuickCart

**Scan. Shop. Pay. Walk Out.**

AI-powered smart supermarket shopping system: barcode self-checkout for customers,
CCTV-based theft detection for retailers. This repo is being built in phases —
see [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) for the full roadmap and status.

## Repo structure (Phase 1)

```
quickcart/
├── backend/                   # FastAPI service
│   ├── app/
│   │   ├── api/v1/            # versioned route handlers
│   │   ├── core/              # config, security, JWT verification
│   │   ├── db/                # Supabase client, session helpers
│   │   ├── models/             # ORM / dataclasses mirroring supabase schema
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── services/           # business logic (cart, checkout, invoicing...)
│   │   ├── ai/
│   │   │   ├── detection/      # YOLOv8 inference wrapper
│   │   │   ├── tracking/       # DeepSORT wrapper
│   │   │   └── theft_logic/    # cart-vs-shelf mismatch rules, alert generation
│   │   └── utils/
│   └── tests/
├── frontend/                   # Responsive PWA (HTML5/CSS3/ES6)
│   ├── public/
│   └── src/
│       ├── components/{customer,retailer,shared}/
│       ├── pages/{customer,retailer}/
│       ├── hooks/ services/ store/ styles/
├── android/                    # Capacitor wrapper around frontend/
├── supabase/
│   └── migrations/             # versioned SQL migrations (source of truth for schema)
├── deployment/                 # Dockerfiles, Vercel/Railway configs
├── scripts/                    # one-off / ops scripts
└── docs/                       # architecture docs, API reference, this roadmap
```

## Why this structure

- **`supabase/migrations/`** is the single source of truth for the database. Nothing
  in the backend defines schema — it only reads/writes against what's migrated here.
  This keeps schema changes reviewable as plain SQL diffs in Git, which matters a lot
  once RLS policies are involved.
- **`backend/app/ai/`** is deliberately separated into `detection`, `tracking`, and
  `theft_logic` as three independently testable stages, matching the pipeline in the
  spec (YOLOv8 → DeepSORT → mismatch logic). This lets you swap the detector or
  tracker later without touching the alerting rules.
- **Service-role isolation**: the backend uses Supabase's service-role key for
  privileged writes (session creation, AI alerts, invoice generation). Direct
  client access from the frontend/Android app uses the anon key and is constrained
  entirely by the RLS policies in the migration — so even if a client is compromised,
  it can only ever see/modify what its role is allowed to.

## Database schema (Phase 1 deliverable)

See [`supabase/migrations/0001_core_schema.sql`](supabase/migrations/0001_core_schema.sql).

Core entities and relationships:

```
auth.users ──1:1── customers
auth.users ──1:1── retailers ──1:N── stores ──1:N── categories
                                   └─1:N── products
                                   └─1:N── cctv_cameras
                                   └─1:N── employee_accounts

customers ──1:N── shopping_sessions ──1:N── cart_items ──N:1── products
                                   └─1:N── payments
                                   └─1:1── invoices
                                   └─1:N── ai_alerts

stores ──1:N── ai_alerts (via cctv_cameras)
```

Design notes:
- All money stored as `BIGINT` paise, never floating point.
- `products.price_paise` is a **generated column** from `mrp_paise` and
  `discount_percent`, so price is always internally consistent — no risk of stale
  cached discounted prices.
- `products.shelf_location` and `cctv_cameras.covers_shelf_locations` are the join
  point between the AI pipeline and inventory: a camera's detections are mapped to
  the products that could plausibly be on the shelves it watches, which is what
  makes cart-vs-shelf mismatch detection (Phase 6) computable at all.
- RLS is enabled on every table. Customers only ever see their own sessions/cart/
  payments; retailers only ever see data scoped to stores they own; CCTV streams
  and AI alerts are never exposed to customer-role clients under any policy.

## Environment variables (used from Phase 2 onward)

```
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
JWT_SECRET=
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
QR_ENCRYPTION_KEY=
```

## Running the schema locally

```bash
# Requires the Supabase CLI
supabase init
supabase link --project-ref <your-project-ref>
supabase db push   # applies supabase/migrations/*.sql in order
```

## Status

Phase 1 (this delivery): repo scaffold + core schema + RLS. ✅
Next: Phase 2 — FastAPI auth skeleton + role-based access middleware.

Suggested commit for this phase:
```
git commit -m "chore: scaffold repo structure + core Supabase schema with RLS (Phase 1)"
```
