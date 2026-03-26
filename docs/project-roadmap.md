# Project Roadmap

## Current Stage
Prototype to early operational system. Core flows exist, but architecture and docs are still being stabilized.

## Phase 1 - Documentation and Cleanup
- Replace outdated Spring Boot references.
- Establish docs as source of truth.
- Remove committed secrets and rotate keys.
- Clarify setup flow for `server/data/.config.yaml`.

## Phase 2 - Reliability Hardening
- Reduce oversized handler complexity.
- Add stronger validation on device and API inputs.
- Track and manage background tasks explicitly.
- Add limits around live stream fan-out and memory usage.

## Phase 3 - Security Hardening
- Enforce real device authentication.
- Remove permissive default device ids.
- Move secrets to environment or external secret store.
- Review Telegram and dashboard command authorization boundaries.

## Phase 4 - Data and Observability
- Replace ad hoc JSON persistence with structured storage.
- Add better health checks and metrics.
- Improve auditability of caregiver and device actions.

## Phase 5 - Product Improvements
- Improve dashboard usability and responsiveness.
- Add better chart accuracy from real historical data.
- Expand caregiver AI guidance with safer domain constraints.
- Add clearer device status and recovery flows.

## Open Issues To Resolve
- Final authoritative config strategy.
- Whether to keep single-process global state long term.
- Whether Telegram should remain long-polling or move to webhook.
- Whether image/stream ingest should be separated into a dedicated service.
