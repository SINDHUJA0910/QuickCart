# QuickCart Deployment Guide

## 1. Supabase (database, auth, storage)

```bash
supabase init
supabase link --project-ref <your-project-ref>
supabase db push   # applies every file in supabase/migrations/ in order
```

After pushing migrations, set these in your Supabase project dashboard:
- **Auth → Email templates**: customize the verification/reset emails if desired
- **Auth → URL Configuration**: set your frontend's redirect URLs
- **Storage**: confirm the `invoices`, `product-images`, `store-images`, and
  `ai-alert-media` buckets exist (created by migration `0002`) with the
  expected public/private settings

Grab from **Project Settings → API**: `SUPABASE_URL`, `anon` key,
`service_role` key. Grab from **Project Settings → API → JWT Settings**:
the JWT secret.

## 2. Backend (Railway)

This repo includes `railway.json` at the root, pointing at
`backend/Dockerfile`. To deploy:

1. Create a new Railway project, connect this repo.
2. Set environment variables (Railway → Variables) matching
   `backend/.env.example`:
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`
   - `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`
   - `QR_ENCRYPTION_KEY` — generate with:
     `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - `ADMIN_API_KEY` — any long random string
   - `CORS_ORIGINS` — your deployed frontend's actual origin(s), comma-separated
   - `APP_ENV=production`
3. Railway builds from `backend/Dockerfile` automatically on push.
4. Confirm `/health` responds once deployed.

Render is a drop-in alternative — same Dockerfile, same environment
variables; Render's dashboard has an equivalent "Docker" service type.

## 3. Frontend (Vercel)

Not yet built as of Phase 8 — this section documents the intended target.
Once the frontend exists: connect the repo to Vercel, set the build output
directory, and set `VITE_API_BASE_URL` (or equivalent) to the Railway
backend's public URL plus `/api/v1`.

## 4. Post-deploy checklist

- [ ] `docker build -f backend/Dockerfile backend/` succeeds locally (see
      `docs/SECURITY.md`'s verification honesty note — this specific step
      was not run in the development sandbox)
- [ ] `/health` returns 200 from the deployed backend
- [ ] A real signup → login → store search round-trip works against the
      live Supabase project
- [ ] CORS_ORIGINS is the real frontend origin, not `localhost`
- [ ] Razorpay keys are the **live** keys, not test keys, before accepting
      real payments
- [ ] `ADMIN_API_KEY` is a real secret, not the placeholder from `.env.example`
