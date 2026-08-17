# QuickCart — Build Roadmap

**Tagline:** Scan. Shop. Pay. Walk Out.

This document tracks the phased build-out of QuickCart. Each phase is delivered as
working files (not pseudo-code), with a suggested commit message, so the repo is
bisectable and reviewable at every step.

## Confirmed stack decisions

| Layer | Choice | Rationale |
|---|---|---|
| Backend framework | FastAPI | Async-native, auto OpenAPI docs, matches spec's "preferred" |
| DB / Auth / Storage / Realtime | Supabase (Postgres) | Single spec requirement, no alternative needed |
| Frontend | HTML5/CSS3/ES6 + a lightweight component layer | Responsive PWA, installable |
| Android | Capacitor wrapping the PWA | One codebase, real native APK, camera/barcode plugin access |
| Barcode | ZXing (native via Capacitor plugin), BarcodeDetector API fallback on web | Reliable on-device scanning without server round-trip |
| Payments | Razorpay, behind a `PaymentProvider` interface | INR-first market fit; Stripe can be added by implementing the same interface |
| AI detection | YOLOv8 (Ultralytics) | Best-supported real-time detector with pretrained weights |
| Tracking | DeepSORT | Standard pairing with YOLO for multi-object tracking |
| Deployment | Vercel (frontend), Railway/Render (backend), Supabase Cloud (DB) | Matches spec |

## Phases

- **Phase 1 — Foundations** *(this delivery)*
  Repo structure, Supabase schema + RLS policies, ERD, environment config, README.
- **Phase 2 — Auth & backend skeleton**
  FastAPI app factory, Supabase JWT verification, customer/retailer auth endpoints,
  role-based access middleware, OpenAPI docs setup.
- **Phase 3 — Customer shopping flow**
  Store search API, shopping session lifecycle, barcode lookup endpoint, cart service.
- **Phase 4 — Checkout, payments, invoice, QR exit pass**
  Razorpay integration, invoice PDF generation, encrypted QR pass, exit validation.
- **Phase 5 — Retailer dashboard**
  Inventory CRUD, live session monitoring, sales analytics endpoints, CSV/PDF reports.
- **Phase 6 — AI theft detection pipeline**
  YOLOv8 inference service, DeepSORT tracking service, cart-vs-shelf mismatch logic,
  alert generation and delivery. Includes an explicit note on what is genuinely
  production-ready out of the box (person/product detection, tracking, rule-based
  mismatch alerts) vs. what requires a labeled dataset and training run you'll need
  to run yourselves (a fine-tuned "concealment gesture" classifier).
- **Phase 7 — Notifications, admin, reporting**
  Supabase Realtime channels, notification service, admin views.
- **Phase 8 — Deployment, tests, security hardening**
  Dockerfiles, Vercel/Railway configs, pytest suite, security checklist.

## Status
Phase 1: ✅ done — repo scaffold + core Supabase schema + RLS.
Phase 2: ✅ done — FastAPI skeleton, Supabase JWT verification, customer/retailer
signup+login+me+forgot-password, role-based access dependencies, 6 passing tests.
Phase 3: ✅ done — store search (haversine distance), shopping session lifecycle
(one active session per customer, enforced), barcode product lookup, cart service
(price snapshotting, live stock sync on add/update/remove). 14 passing tests total.
Phase 4: ✅ done — Razorpay order creation + server-side signature verification
(never trusts client-claimed success), real PDF invoice generation (ReportLab)
uploaded to Supabase Storage, Fernet-encrypted time-limited QR exit pass,
retailer exit-scan endpoint with store-ownership + replay checks. 23 passing
tests total; sample invoice PDF and QR image visually verified.
Phase 5: ✅ done — retailer store CRUD, inventory management (product/category
CRUD, valid EAN-13 barcode auto-generation, soft-delete, low-stock detection),
live dashboard stats computed from real data, live session monitoring, recent
transactions, CSV export, top-products/peak-hours reports. Store-ownership
enforced centrally via one shared helper across every retailer endpoint.
32 passing tests total. 39 routes registered.
Phase 6: ✅ done — real YOLOv8 person detection (verified against an actual
photo, correct detections), real DeepSORT multi-person tracking (verified
stable track IDs across frames for 1 and 2 simultaneous people), classical-CV
shelf-activity detection via frame differencing (verified: ignores static
scenes, flags real pixel changes, independent per zone), cart-vs-shelf
mismatch engine implementing spec Scenarios 1/2/5 at the count level (with an
explicit guardrail refusing to attribute alerts when multiple customers are
concurrently active at a store), camera CRUD with pixel-ROI zone config,
AI alert CRUD, and a full frame-ingestion endpoint tested end-to-end against
a real photo (3 people tracked, camera heartbeat updated). 39 passing tests.
Explicit scope limitation carried forward honestly: product-level identity
("which SKU was picked") and concealment-gesture recognition need a labeled
training run this environment can't fabricate — documented in the code
rather than faked.
Phase 7: ✅ done — notifications wired at real trigger points (low-stock and
out-of-stock fire exactly when a scan crosses the threshold, not on a
periodic scan; payment success notifies both retailer and customer; AI
alert creation notifies the retailer), backed by Supabase Realtime
(migration 0004 enables replication — no custom websocket server needed,
frontend subscribes directly via postgres_changes). Notification read/unread
state and per-recipient ownership enforced. Admin views (platform stats,
store listing, system health) gated behind a documented MVP-level shared
admin key, matching the spec's "Optional" status for this feature.
48 passing tests, 50 routes registered. One real regression caught and
fixed: adding notification triggers broke 3 earlier-phase tests whose fake
fixtures predated the new code paths — fixed by patching the missing
fixture modules and adding a defensive default matching the DB schema's
actual default value, not by weakening the app code.
Phase 8: ✅ done — closed the two gaps flagged as known limitations in
earlier phases: stock adjustment now goes through an atomic Postgres RPC
(`adjust_product_stock`, migration 0005) instead of read-then-write, and a
DB-level partial unique index enforces one-active-session-per-customer as
a safety net under the application check. Added rate limiting (slowapi) on
auth and checkout, verified to actually return 429 on the 4th request in a
window, not just assumed. Added production Dockerfile (multi-stage,
non-root, CPU-only torch to avoid ~2GB of wasted CUDA packages — a real
issue caught while testing the requirements.txt install), docker-compose
for local dev, Railway config, a CI workflow that runs the real test suite,
a deployment guide, and an honest security checklist audited line-by-line
against the spec's requirements (including the gaps that remain, not just
what's done). 50 passing tests total.
Explicitly NOT done and flagged rather than silently skipped: the
Dockerfile was not actually built in this sandbox (no Docker daemon
available) — verified requirements.txt resolves cleanly instead, and
documented the one unverified step plainly in docs/SECURITY.md. The
frontend PWA, Android Capacitor wrapper, and invoice email delivery were
never started — the effort so far has been backend-API-first across all
8 phases.
Next steps if continuing: frontend (HTML/CSS/ES6 PWA per the spec),
Android wrapper (Capacitor), invoice email delivery (Supabase Edge
Function or a transactional email provider), and — if it becomes a real
priority rather than staying "Optional" — upgrading admin auth from the
current MVP shared-key model to real admin accounts.

Frontend Phase 1 (landing page): ✅ done — self-contained responsive
HTML/CSS/JS landing page (frontend/public/index.html) with dark/light mode,
glassmorphism nav, and an interactive signature element (a scan-beam demo
that visually distinguishes normal barcode scans from an unscanned item
triggering a theft alert — demonstrating the core value prop directly
rather than describing it). Design grounded in real retail/POS signage
vocabulary (barcode stripes, receipt line-items, price-tag cards) rather
than generic SaaS-landing-page defaults.
Verified with actual rendering, not assumed: used Playwright (real
Chromium) to screenshot every section in both themes and at mobile width.
Caught and fixed three real issues this way: (1) Google Fonts requests
were blocked in the dev sandbox (403), which was masking two further
problems — switched to self-hosting the three typefaces via @fontsource
(160KB total), which is also better production practice (no third-party
request, no FOUC, works offline); (2) the scroll-reveal animation could
leave content permanently invisible if IntersectionObserver never fired —
rewritten so content is visible by default and JS only progressively
enhances it; (3) the mobile nav bar clipped its primary CTA button off
-screen at 390px width — fixed with a dedicated narrow-viewport breakpoint.
Next: customer-facing app screens (store search, barcode scan, cart,
checkout, QR pass) and retailer dashboard UI, both wired to the Phase 1-8
backend API.

Frontend Phase 2 (customer app): ✅ done — full customer-facing flow as
static HTML/CSS/ES6 pages wired to the real backend API: login/signup
(role toggle for customer/retailer), store search, session creation,
barcode scan (native BarcodeDetector with a ZXing CDN fallback, plus
manual entry for damaged/unreadable barcodes), product detail + add-to-
cart, live cart with quantity steppers, checkout with real Razorpay
integration, and the QR exit-pass success screen. Shared design system
(assets/css/app.css) reuses the landing page's brand tokens.
Verified with a genuine end-to-end integration test, not just code
review: ran the actual FastAPI backend (Supabase faked out the same way
the pytest suite does) alongside the actual frontend files, both served
over real HTTP, and drove the full flow with Playwright — including a
client-side stub that computes a REAL HMAC-SHA256 signature so the
backend's actual payment-signature-verification code path was genuinely
exercised end-to-end, not skipped. All 15 checks passed: signup, store
search rendering real seeded data, session creation, barcode lookup
returning correct price/discount/stock, cart totals matching backend
calculation exactly, bill persisting correctly across a page navigation,
and a successful payment producing a real invoice number and real QR PNG.
Two real bugs were caught and fixed by this process (not found by
inspection): (1) unhandled backend exceptions returned a bare 500 with no
CORS headers, which browsers report as a confusing "CORS error" masking
the real problem — added a catch-all exception handler in main.py that
logs the real error server-side and always returns through the normal
response path so CORS headers are preserved; (2) the test harness's
seed() helper bypassed the products table's generated-column logic,
causing a KeyError — fixed in tests/fake_supabase.py's seed() method
itself so this class of bug can't recur in any test that uses it.
Next: retailer dashboard UI (inventory, live sessions, AI alerts,
reports) and the Android Capacitor wrapper.

Frontend Phase 3 (retailer dashboard): ✅ done — full retailer-facing UI:
store setup (for new retailers with no store yet), dashboard (live stats,
recent transactions, top products, peak hours, CSV export), inventory
(add/edit/delete products with auto barcode generation, low-stock filter),
live sessions monitoring, and AI alert management (resolve / mark false
positive). Multi-store support via a store switcher that persists the
selected store across pages. Shared retailer chrome (topbar, store
switcher, tab nav) factored into one module (retailer-shell.js) rather
than duplicated across 4 pages.
Verified the same way as the customer app — a real end-to-end Playwright
run against the real backend (fake Supabase underneath): retailer signup
-> store creation -> dashboard stats -> add a product -> verify the
backend's real discount calculation and real EAN-13 generation -> low-stock
filter round-trip -> live sessions and alerts screens load cleanly -> dark
mode persists across navigation. All 15 checks passed; combined with the
customer flow's 15, that's 30 real end-to-end checks across the app.
Two real bugs caught by this process: (1) my own test harness only mocked
the Phase 1-4 service modules, never extended when the retailer UI was
built against the Phase 5-7 services — fixed by patching all of them; (2) a
genuine CSS bug — the retailer topbar used a different class
(.retailer-topbar) than the customer topbar (.topbar), so the shared
".topbar .logo" style rule silently didn't apply, leaving the retailer
logo with a stray browser-default underline. Fixed the CSS selector to
cover both, verified with a before/after screenshot.
Next: Android Capacitor wrapper, and closing remaining spec items
(invoice email delivery, admin UI).

Closing items (fast pass): ✅ done —
1. **Invoice email delivery**: SMTP-based (provider-agnostic — works with
   SendGrid/Resend/Postmark/SES via their SMTP endpoints), wired into
   checkout confirmation. Fails open: if SMTP isn't configured, checkout
   still succeeds and just skips the email — verified with a smoke test
   (no exception, returns False cleanly).
2. **Admin UI**: single-page console (platform stats, all-stores table,
   system health) gated by the existing X-Admin-Key backend auth.
   Verified end-to-end against the real backend.
3. **Android wrapper**: Capacitor config + package.json with real,
   version-checked-against-npm current package pins (Capacitor 8.5.0).
   The native android/app project itself is intentionally NOT committed
   (it's toolchain-generated via `cap add android`, not hand-written) —
   README explains why and gives exact setup commands. Barcode scanning
   needs no native plugin: the existing BarcodeDetector/getUserMedia code
   in shop.html works directly in the Capacitor WebView; @capacitor/camera
   is included so its Android manifest merge grants camera permission
   automatically.

## Overall status

All original spec deliverables are now addressed: backend (8 phases, 50
tests), customer app, retailer dashboard, admin console, Android wrapper
config, and invoice email delivery. Two things remain honestly
out of scope for a from-scratch build in this format: (1) a fully trained
concealment-gesture classifier — the harness exists
(scripts/train_concealment_classifier.py) but needs real labeled footage
only the retailer can provide; (2) production deployment itself (running
`docker build`, provisioning a real Supabase project, real Razorpay keys)
— everything needed to do that is documented in deployment/README.md, but
actually deploying requires credentials this environment doesn't have.
