# Global Estates — Product Requirements & Delivery Record

## Original problem statement
Build and deploy a complete production-ready Global Estates international property marketplace. Visitors rent homes, reserve vacation accommodation and outings, discover land for sale, save favorites and contact owners. Authenticated owners list/manage properties and see bookings, listing plans, commission-adjusted earnings and real payout status. Homepage must have working backend search, category and worldwide country discovery, polished image cards, functional navigation and excellent Android/mobile layouts. Original specification requested PostgreSQL, DATABASE_URL, Google/existing authentication, Stripe Checkout/webhooks, 10% commission for Vacation/Outings, configurable rental fee, Free KSh0 / Featured KSh500 / Premium KSh2000, land inquiry rather than online title transfer, rigorous button testing, and publication only after tests. Preserve existing working routes and integrations.

## Explicit user choices / changes
- Dark modern interface, emerald and gold accents, light text, polished property cards, professional typography, mobile-first; “Make it look nice”; “Keep it global”.
- Google AND email/password authentication.
- Clearly labeled database-backed sample listings, not bookable.
- Latest database instruction: **“replace PostgreSQL with MongoDB.”** This supersedes earlier PostgreSQL insistence. MongoDB is the actual database, not PostgreSQL.
- Owner identity: **masoudhussein2002@gmail.com**. Reserved in users with name Masoud Hussein, no default password or authentication bypass. Google verification required to access this reserved identity.
- Stripe recommended claimable sandbox selected. Provisioning was attempted through the official integration flow; terminal response `400 country_not_supported`, country `KE`. Never fall back to preinjected STRIPE_API_KEY or fabricate success.

## Personas
1. Anonymous international visitor discovering properties by location, country, type, price and capacity.
2. Authenticated customer saving favorites, messaging hosts, checking dates and viewing trip/payment status.
3. Authenticated owner managing only their own listings, inquiries, bookings, plans and earnings.

## Architecture decisions
- React 19 + React Router; shared provider for identity, favorites and marketplace metadata; shadcn Button/Dialog; Sonner notifications; Lucide icons.
- FastAPI modular routes: auth.py, catalog.py, owners.py, payments.py, storage.py; core.py shared configured Mongo connection/ownership authorization; Pydantic request and response schemas; seeds.py idempotent indexes and samples.
- Database only via existing MONGO_URL/DB_NAME. Public projections and schemas exclude Mongo ObjectId/private owner email. Collections users, user_sessions, hosts, properties, bookings, availability, favorites, inquiries, payment_transactions, files, auth_limits, status_checks.
- Credentials only backend environment. HTTPS secure HttpOnly SameSite=None sessions, SHA-256 token hashes, bcrypt passwords, seven-day expiry; limited login attempts. Ownership stamped server-side and checked in every owner modification query.
- Origin validation allows only configured public origin, exact routed Host and exact X-Forwarded-Host. Managed preview ingress rewrites Origin to internal routed hostname; initial defect fixed and regression-covered.
- Managed object storage stores real images; backend validates bytes/type/10MB limit, saves canonical storage references, and serves public listing media.
- Stripe SDK implementation guarded by STRIPE_SECRET_KEY. No usable sandbox could be provisioned for Kenya. Online checkout, paid promotions, Connect onboarding and payouts are therefore disabled/unavailable. No mocked APIs or fake payments.
- Fees calculated server-side: vacation10%, outings10% (days × guests), rent configured0% (30-day periods rounded up). Prices are KES. Stripe code selects tax calculation at checkout (not activated or verified because Stripe is blocked).
- Booking availability uses unique property/date inventory records and timed holds. Land is inquiry-only. Samples reject bookings/inquiries server-side.
- Preserve template /api/ and /api/status routes. Health reports actual Mongo/Stripe status without exposing secrets.

## Implemented — 2026-10-01
- Branded full-bleed homepage, responsive desktop/mobile navigation, database search including Enter, homepage category/country filters, View All/Explore Stays/destination navigation.
- Browse page with global countries, location/category/price/bedrooms/guests filters, sort, paging, loading/error/empty states and working filter toggle.
- Eight illustrative sample listings (Kenya, Tanzania, Indonesia, France) stored in MongoDB, visibly labeled, non-bookable; no fake owner contact.
- Property detail galleries, capacity/amenities/host, favorite controls, actual inquiry inbox flow, quote availability and validation, safe payment-unavailable state.
- Email registration/login/logout/session persistence fully browser-tested. Google redirect and server exchange implemented; external Google completion not verified because provider page produced external404/CORS errors and requires real user login.
- Authenticated listing create/edit/pause/reactivate/delete, HTTPS image URLs plus real file uploads. Immediate visibility for new active listings; private paused owner preview.
- Owner dashboard: scoped properties, bookings, inquiries, revenue/earnings/payout totals from actual data, safe plan/payout controls; customer saved places and trips.
- Free/Featured/Premium plan screen; no paid badge upgrades without confirmed payment. Guarded Stripe checkout/status/webhook/Connect/transfer code is **not end-to-end verified or operational**.
- Premium dark emerald/gold visual system; real Unsplash assets; purposeful Playfair Display/DM Sans fonts; responsive forms/cards/modals; accessible focus/loading/disabled states.
- SEO title/description and mobile theme color.

## Verification — 2026-10-01
- `yarn build` successful; backend compileall successful.
- External API pytest:15/15 passing. Tests include valid browser Origin, authentication, health, DB filters/privacy, ownership denial, favorites, inbox delivery, quote/date/commission rules, real file upload/download, safe503 Stripe failures.
- Browser: register/login/logout, owner CRUD, pause-preview/reactivation, dashboard tabs, gallery, favorites, customer inquiry/owner inbox, booking quotes, disabled payment notices, public search/nav and mobile hamburger all passed.
- Tested1920×800 desktop and390×844 mobile, including populated owner/detail/form/contact screens. Mobile Sonner overflow fixed; regression shows no horizontal overflow.
- Reports `/app/test_reports/iteration_1.json` (initial auth-Origin defect), `/app/test_reports/iteration_2.json` (fixed, no app-code bugs). Test listings cleaned up. Test accounts may remain and are not business data.
- No claim of actual Google OAuth completion, paid checkout, webhook payment confirmation, Stripe transfer or bank payout verification.

## Prioritized backlog / next actions
### P0 — external launch blockers / limitations
1. Resolve payment provider availability for Kenya: official Stripe sandbox provisioning is terminally unsupported for the platform country. Any alternate provider requires explicit user choice and integration. Do not retry unchanged or use shared fallback credentials.
2. Verify real-user Google sign-in through the external provider. Email/password flows for ordinary users are proven; reserved owner uses verified Google identity.
3. Complete final static deployment readiness check and requested publication/charge confirmation, recording resulting URL/status here. Do not label preview as production.
### P1 — before enabling money movement
- Provision valid payment provider, complete onboarding; implement/verify provider tax catalog and account setup, checkout paid/cancel/failed/webhook/replay/refund, concurrent availability and late confirmation reconciliation, plan fulfilment, Stripe Connect eligibility/cross-border rules and idempotent transfer recovery using real test transactions.
- Confirm rental fee0% and 30-day billing as business policy; add refund/cancellation rules and host terms before accepting live bookings.
### P2 — optional improvements
- Owner email notifications for inbox messages (currently delivered to actual dashboard inbox only; no email delivery claims).
- Currency localization, verified-owner badges and reviews to improve trust/conversion; richer map/location search.
- Password reset and email verification; owner account password setup after verified Google sign-in.

## Delivery status
Marketplace browsing, ownership CRUD, inquiries, saved places, real uploads and email auth are implemented and tested. Paid reservations, paid promotions and payouts are explicitly unavailable, not mocked or successful. Production publication status pending final readiness and deployer response.
