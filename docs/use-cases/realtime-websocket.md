# Real-time WebSocket live stream

## Use case

**Who:** sportsbook, media, and trading teams using BETMAN_DATA in live mode.

**What:** Push live race and market events over WebSockets instead of relying only on polling.

**Why:** A “nerve centre” product loses value if everything is pull-only and stale between polls.

### User stories

- As a live operator, I need the webapp to react faster to market and race events.
- As an integrator, I need the same tenant key model to secure WebSocket access.
- As an engineer, I need graceful behaviour when Redis is empty or unavailable.

## Business case

- improves perceived speed and premium feel for licensees
- reduces wasteful polling over time
- closes the gap between platform positioning and actual live-delivery capability

## First implementation

- `/v1/live/{feed_id}` now exists as an authenticated WebSocket endpoint
- the API listens to Redis pub/sub channels and falls back to heartbeat-only mode when needed
- the webapp opens a live socket in Live mode and invalidates key queries on incoming events
- nginx is configured for WebSocket upgrade headers
