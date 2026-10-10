# FUT-05 — Enterprise accessibility and versioned pricing offers

Tracks [issue #79](https://github.com/aradenac/AI-Compass/issues/79), the authoritative [Accessibility & Pricing specification](future-evolutions/technology-accessibility-and-pricing.md), and the dependency on FUT-03 (#77). This release **does not implement metered Run cost calculation**: that belongs to FUT-09.

## Data / authority

- **Catalog enterprise access**: each existing Model, Provider, Harness and Framework can carry `properties.enterprise_accessibility` (enum `accessible`, `restricted`, `not_accessible`, `unknown`) in a fresh immutable component revision. A missing/old field is projected as **unknown**, not an inferred status. This is a shared enterprise fact **not a user entitlement or right to access credentials**. The old `accessible` boolean and free-text `pricing` properties remain historically readable and are not silently promoted.
- **Offers**: every `off-<codename>` identity is a `pricing_offer` CatalogItem with immutable `CatalogRevision`, explicit component linkage, billing owner, ISO currency, cited source, date checked, optional effective dates, status and cumulative billing `lines`. Alternative offers are distinct identities. A revised price appends a new revision; editing does not rewrite an original charge, Run or campaign. There is no supplied/priced seed offer on an empty Server.
- **Charge lines**: exact `charge_id`, family `free|token|credit|request|time|usage|tiered|subscription|per_seat|hybrid|negotiated`, classification `free|fixed|variable|unknown`, optional period for fixed fees, explicit meter and denominator for variable rates, exact decimal rate (or null/incomplete), provider-namespaced credits, optional ascending tiers and bounded applicability. Fixed recurring commitments remain **outside the marginal Run meter list**, while hybrid plans expose only explicitly defined variable lines. Shared enterprise credit balances, allowances or invoices are **never** tracked.
- **Campaign selection**: a contributor must explicitly choose a single alternative offer revision for every billable technical source (`root:model`, `root:provider`, `root:harness`, `root:framework`, or `ptp-...:model|provider|harness`). The selected tuple `source_key + component_id + offer_id + offer_revision_id` is snapshotted as **immutable FK-protected CampaignPricingPin** rows for the corresponding CampaignSnapshot. No offer is selected automatically, and no offer is part of the technical AI Solution identity. A billing owner + charge ID may not be counted twice **within one invocation** (root Model/Provider/Harness or one participant); different participants remain separately billable invocations.
- **Session-specific dynamic trios**: a Task-centred Campaign without a Framework cannot know its Model/Provider/Harness until an individual Test Case session is started. Its campaign projection returns `requires_session_pricing`, and the session-creation form requires one manually chosen immutable offer revision per selected Model/Provider/Harness. These references are frozen as relational `SessionPricingPin` FKs on the session. A pricing-incomplete individual session is rejected. Framework and solution-centred sessions inherit their already pinned Campaign offer revisions, and cannot override them. Historical pre-FUT-05 sessions are unchanged.
- **Readiness**: `pricing_readiness` on the existing Campaign JSON reports exact missing sources, out-of-date/incomplete offers, required meters, separate fixed commitments and currency set. A draft Campaign is allowed while incomplete. An **opted-in** `pricing_policy=offer_revisions_v1` Campaign has new Test Case session creation blocked until complete. Campaigns made with the historical API (without `pricing_selections`) keep their existing legacy manual-cost behavior; they are clearly labeled `legacy_unclassified` instead of being falsely backfilled. Revising an existing campaign never silently chooses or repins an offer.

## HTTP contract

Authenticated, CSRF-checked and permission-protected, consistent with other existing `/api/v1` routes:

| Endpoint | Reader | Workgroup contributor |
| --- | --- | --- |
| `GET /api/v1/pricing/offers[?component_id=...]` | Available | Available |
| `POST /api/v1/pricing/offers` | Forbidden | Create, explicit source/rates |
| `GET /api/v1/pricing/offers/<off-id>` | Available | Available |
| `PATCH /api/v1/pricing/offers/<off-id>` | Forbidden | Full version replacement with `expected_revision`, 409 on conflict |
| `GET /api/v1/pricing/offers/<off-id>/revisions[/<number>]` | Available | Available |
| `GET/PATCH /api/v1/pricing/access/<model|provider|harness|framework>/<public-id>` | GET only | Changes create exact catalog revision |

All endpoints fail closed on missing auth, invalid inputs, unknown historical schema, foreign IDs or revision mismatch. Pricing owner/component linkage cannot be moved to an unrelated item by editing an offer.

## UI / workflow

Open the **Technology Catalog** in Demo or Server to see the same `shared-pricing.js` offer editor and enterprise status selector. Demo records are expressly fictional and stay in its original browser-local database; no Server API is called. Server updates go only to Django/PostgreSQL and require workgroup write permission.

In Server Benchmark Workspace → Campaign create/edit, first choose the actual technical configuration; select the appropriate offer revision for each root component or framework participant. New Framework participants receive their permanent public IDs **on first Campaign save**; save that draft and then pin their individual offers in a subsequent Campaign revision. Source/offer mismatch or duplicate invoice lines is rejected transactionally. A pricing offer may be changed later without altering a previous Campaign pricing snapshot.

No per-Run usage-entry form, FX default, negotiated unknown amount valuation, accounting subscription allocation, shared quota subtraction or reported achieved savings is added by FUT-05. Those remain governed by FUT-09 and later economic features. Rates and quantities remain unit/currency labeled, not automatically converted across currencies.

## Tests and operations

Run backend tests with `python manage.py test config.test_pricing` (Django test database) and browser-free presentation checks with `node scripts/test-pricing-frontend.js`. CI includes these alongside existing Demo/Server compatibility, archive, migration staging, data-integrity and coordinated-release checks.

Migration `0023_pricing_offers.py` is **additive**: one immutable schema registry row and one immutable FK-protected table, no forced backfill. Previous releases can still read their original business objects after normal forward migration; rollback to a previous frontend/backend should use the **previous verified coordinated artifacts and an appropriate pre-migration DB snapshot**, never manually remove immutable offer history. Historical price unknowns remain unknown.

**Operational gates:** the generic PLAT signed production staging/recovery/approval gates remain **NO-GO**; a green automated smoke suite does not authorize production promotion.
