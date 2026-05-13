---
name: weather
description: Check current weather or forecast for a city using wttr.in through a read-only curl command.
metadata: {"echo":{"emoji":"weather"}}
---

# Weather

Use this skill when the user asks about weather, temperature, rain, forecast, or phrases like "查天气".

## Workflow

1. Identify the location. If the user does not provide one, ask a short clarification.
2. Call the generic tool:

```json
{"command": "curl wttr.in/Tokyo?format=j1"}
```

Replace `Tokyo` with the requested city. Use URL-encoded city names when needed.
3. Read the JSON result and answer in Chinese unless the user used another language.
4. Include current temperature, feels-like temperature, condition, rain chance if available, and a brief clothing/umbrella note.

## Output

Keep the result compact:

- Location and current condition
- Temperature and feels-like
- Near-term forecast
- Practical note
