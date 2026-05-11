# Shinobu Chat Frontend

Independent React/Vite frontend for ShinobuChat with a QQ-style chat window and a browser-hosted desktop pet surface.

## Run

```bash
npm install
npm run dev
```

The dev server listens on `http://localhost:5175` and proxies `/api` to the FastAPI backend at `http://127.0.0.1:8000`.

## Asset Import Folders

- `public/assets/live2d/`: Live2D model folders with per-folder `manifest.json`.
- `public/assets/backgrounds/`: stage backgrounds and `manifest.json`.
- `public/assets/music/`: music files and `manifest.json`.
- `public/assets/icons/`: custom icons for avatar tools or buttons.

See `public/assets/README.md` for the exact manifest shape.
