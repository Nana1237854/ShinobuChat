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

## Voice Integration

Voice input posts browser `MediaRecorder` audio to `/api/v1/voice/asr`. Set `SC_ASR_ENGINE=whisper` with `SC_WHISPER_API_KEY`, or set `SC_ASR_ENGINE=funasr` with `SC_FUNASR_API_URL`.

Voice output posts assistant replies to GPT-SoVITS at `SC_GPT_SOVITS_BASE_URL` (default `http://127.0.0.1:9880`). Copy `voice_reference_audio.example.json` to `voice_reference_audio.json` at the repo root, then replace each `ref_audio_path` and `prompt_text`; ShinobuChat chooses the closest preset from the active emotion (`happy`, `sad`, `angry`, `thinking`, `neutral/default`).
