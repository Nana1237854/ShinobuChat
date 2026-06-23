# ShinobuChat Frontend Update

## Summary

Implemented the latest UI concept for ShinobuChat while keeping the existing frontend business logic, API calls, SSE message flow, Live2D asset loading, and backend untouched.

## Changes

- Reworked the main app shell into a three-column layout:
  - collapsible ChatGPT-style sidebar
  - central Live2D stage
  - right-side Shinobu chat panel
- Moved conversation history into the left sidebar.
- Added sidebar entries for new chat, search chat, history, character/model, scene/music, and more/settings.
- Added smooth sidebar expand/collapse transitions.
- Fixed collapsed sidebar icon alignment by using a single 34px center track.
- Restyled the right chat panel to match the concept:
  - lighter panel surface
  - softer message area
  - cleaner assistant and user bubbles
  - bottom-pinned composer
- Updated the message composer with a plus action, compact input styling, and Shinobu AI footer text.
- Fixed existing mojibake in visible Chinese frontend text.
- Added Live2D resize synchronization with `ResizeObserver` so the model does not stretch during sidebar changes.

## Verification

- `npm run typecheck`
- `npm run build`
- `npm test`

## Excluded

- Hidden/generated files such as `.git`, `.env`, `__pycache__`, temporary Vite logs, and build output were not included.
- Existing deleted Live2D asset files shown by `git status` were not part of this frontend layout change and were not staged.
