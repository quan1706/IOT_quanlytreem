# Code Standards

## General Rules
- Keep backend code Python-first and asyncio-safe.
- Prefer small focused handlers over large mixed-responsibility methods.
- Keep user-facing strings in configuration/template files where practical.
- Preserve Vietnamese UX copy unless there is a reason to standardize.

## Python Standards
- Follow PEP 8 where it does not fight readability.
- Use explicit names over cryptic abbreviations.
- Keep functions single-purpose.
- Avoid hidden global coupling unless required by existing architecture.
- Wrap external API calls with clear error handling and logging.

## Async Standards
- Do not block the event loop with CPU-heavy or sync network work.
- Use `run_in_executor` for blocking SDK calls when needed.
- Prefer bounded queues or backpressure for stream fan-out.
- Track background tasks that outlive the request that created them.

## State Management
- Treat `DASHBOARD_STATE` as shared mutable state; update it through helper methods.
- Persist only the minimum required data.
- Avoid adding new global mutable structures without clear ownership.

## API Standards
- Validate request payloads early.
- Return explicit JSON errors for client failures.
- Keep route names consistent under `/api/...`.
- Document new routes in `docs/system-architecture.md` and `docs/codebase-summary.md`.

## Security Standards
- Never commit real secrets.
- Prefer override config in `server/data/.config.yaml`.
- Validate device identifiers and auth tokens strictly.
- Avoid permissive fallback identities for devices.

## Frontend/Dashboard Standards
- Keep dashboard interactions simple and operational.
- Favor readable status labels over decorative UI complexity.
- Preserve quick-action workflow for caregivers.

## Firmware Standards
- Keep pin mappings and hardware assumptions explicit.
- Avoid blocking delays in logic paths unless hardware timing requires them.
- Log key state transitions to Serial for field debugging.

## Documentation Standards
- Update docs when routes, config keys, startup steps, or architecture change.
- Keep docs aligned with the real Python implementation, not old design notes.
