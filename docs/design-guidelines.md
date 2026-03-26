# Design Guidelines

## Product UX Principles
- Optimize for speed during alerts.
- Keep caregiver actions obvious and low-friction.
- Show current baby state, device state, and next action clearly.
- Prefer operational clarity over decorative complexity.

## Telegram UX
- Critical alerts first, controls second, explanation third.
- Use inline buttons for immediate actions.
- Keep command names short and predictable.
- Use Vietnamese copy consistently.
- Avoid long AI answers when the user intent is device control.

## Dashboard UX
- Keep primary metrics visible: cry status, pose, temp, humidity, mode.
- Show action logs and system logs near controls.
- Use charts for trend context, not as the only status source.
- Ensure controls map directly to device commands.

## Safety Messaging
- Dangerous pose alerts must be high-contrast and explicit.
- Distinguish warning vs info states clearly.
- Do not bury urgent advice behind AI verbosity.

## Content Guidelines
- Use warm, concise Vietnamese wording.
- Device control replies should confirm action, not over-explain.
- Analytical responses should summarize state, risk, and next action.

## Technical Design Constraints
- Current dashboard is server-rendered static HTML from `server/dashboard_draft.html`.
- Current Telegram UX depends on `server/config/telegram_config.yaml` for strings.
- Any redesign should preserve compatibility with current route and command model.
