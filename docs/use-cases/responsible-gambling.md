# Responsible gambling and compliance guardrails

## Use case

**Who:** BETMAN licensees operating in NZ, AU, UK, and similar regulated markets.

**What:** Every tenant skin and assistant response needs responsible-gambling messaging, age-gate metadata, and auditable admin actions.

**Why:** BETMAN_DATA is betting-adjacent infrastructure. Even when positioned as data and insights, compliance guardrails are table stakes.

### User stories

- As a licensee, I need jurisdiction-specific messaging for every branded experience.
- As a compliance lead, I need sensitive admin actions recorded in an audit trail.
- As a product team, I need the API to clearly state that BETMAN insights are not betting advice.

## Business case

- reduces regulatory and reputational risk for the licensing model
- makes enterprise procurement easier for operators and media partners
- differentiates BETMAN_DATA as a safer OEM platform, not just a feed API

## First implementation

- `/v1/compliance/rules` exposes jurisdiction metadata and responsible-gambling messaging
- `/v1/skins/{tenant_slug}` now returns compliance metadata for age gates and disclaimers
- assistant responses and the webapp footer surface a “data and insights, not betting advice” disclaimer
- admin key actions write to `audit_log`
