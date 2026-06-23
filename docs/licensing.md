# BETMAN_DATA OEM Licensing Model

BETMAN_DATA is licensed to betting operators, content providers, and data
distributors as a white-label racing intelligence platform. The licensing model
is built around the Skin Engine (see `docs/data-model.md` — Domain 5).

---

## License Tiers

### Tier 1 — Data Feed
Access to structured race, odds, and results data via the BETMAN Data API.

**Includes:**
- `GET /v1/races`, `GET /v1/races/{id}`, `GET /v1/runners/{id}`
- Odds history and tote pools
- Race timeline events
- Standard authentication (1 API key)

**Does not include:** commentary replay, proprietary scores, skin engine,
discovery patterns, or heatmap data.

---

### Tier 2 — Intelligence
Full data feed + BETMAN proprietary scores and market signals.

**Includes everything in Tier 1, plus:**
- `GET /v1/intelligence/races/{id}/scores`
- `GET /v1/market/steamers`, `/smart-money`
- `GET /v1/discovery/patterns` (top-level only)
- `GET /v1/tracks/{name}/barrier-analysis`
- Score leaderboard

**Does not include:** Skin Engine, custom feeds, raw heatmap data.

---

### Tier 3 — Platform (OEM)
Full platform with white-label branding, custom feeds, and admin access.

**Includes everything in Tier 2, plus:**
- Skin Engine (`GET /v1/skins/{tenant_slug}`)
- Custom video/audio feed configuration per skin
- Admin API for managing assets, ad placements, skin contexts
- Commentary replay (`GET /v1/races/{id}/replay`)
- Race story generation (`GET /v1/races/{id}/story`)
- Excitement score visualisation
- Multiple API keys per tenant
- Usage reporting
- WeatherLink data (if licensed separately)
- Heatmap data (if available for jurisdiction)

---

## Tenant Onboarding

### 1. Create the Tenant

Via the Admin API (requires `ADMIN_API_KEY`):

```http
POST /v1/admin/tenants
Content-Type: application/json
X-API-Key: {admin_key}

{
  "name": "Racing.com",
  "slug": "racingcom",
  "tier": "platform",
  "contact_email": "api@racing.com",
  "active": true
}
```

### 2. Create a Skin

```http
POST /v1/admin/skins
Content-Type: application/json
X-API-Key: {admin_key}

{
  "tenant_id": 1,
  "name": "Racing.com Default",
  "slug": "racingcom-default",
  "primary_color": "#e8003d",
  "secondary_color": "#ffffff",
  "font_family": "GT-Walsheim",
  "logo_url": "https://cdn.racing.com/logo.svg",
  "active": true
}
```

### 3. Issue an API Key

```http
POST /v1/admin/tenants/{tenant_id}/api-keys
Content-Type: application/json
X-API-Key: {admin_key}

{
  "label": "Production Key",
  "scopes": ["read", "replay", "scores"],
  "rate_limit_rpm": 1000
}
```

The response includes the raw key **once**. Store it securely — BETMAN never stores
plaintext keys.

### 4. Assign Feeds

```http
POST /v1/admin/tenants/{tenant_id}/feeds
Content-Type: application/json
X-API-Key: {admin_key}

{
  "feed_id": 1,
  "custom_url": null,
  "active": true
}
```

For custom feed URLs (Tier 3 only), set `custom_url` to the operator's own HLS stream.

---

## Skin Context Resolution

The Skin Engine supports hierarchical context overrides. Priority (highest wins):

| Context | Example Use Case |
|---|---|
| `race` | Custom overlay for a specific G1 race sponsorship |
| `meeting` | Meeting sponsor branding for all races at a track |
| `race_class` | Black type races always show premium skin |
| `global` | Default brand for all content |

---

## Ad Slot Management

Each skin supports configurable ad slots, allowing operators to sell advertising
within their BETMAN-powered product.

**Default slot types:**
- `banner_top` — full-width top banner
- `sidebar_right` — right-panel sidebar
- `pre_race_video` — video pre-roll before race replay
- `parade_ring_overlay` — overlay during parade ring coverage
- `results_banner` — banner shown on results screen

Ad placements are managed via:
```http
POST /v1/admin/skins/{skin_id}/ad-placements
```

---

## Billing and Usage

All API requests are logged to `tenant_usage` (anonymised, aggregated daily).
Usage reports are available via the admin API.

Billing is handled externally (invoice or usage-based). The usage data in
BETMAN_DATA provides the raw numbers.

---

## Revenue Model Summary

| Stream | Description |
|---|---|
| License fees | Monthly/annual per-tenant license by tier |
| API call overage | Charged above plan request thresholds |
| Ad revenue share | Optional rev-share on ad placements in skin |
| Premium data | Heatmap, discovery patterns, smart money as add-ons |
| White-label setup | One-off onboarding fee for OEM integrations |

---

## Supported OEM Operators (Target)

- Racing.com (Australia)
- Ladbrokes Australia / New Zealand
- TAB NZ
- William Hill (ANZ)
- Sportsbet
- NZRB-affiliated content partners
- Independent racing data aggregators

Each operator receives a branded skin, dedicated API key set, and their own
feed configuration. BETMAN_DATA handles the data; operators handle their own UI.
