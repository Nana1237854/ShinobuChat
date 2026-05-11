# Shinobu Asset Import Guide

Put your runtime assets here. Files under `public/` are served from `/assets/...`.

## Live2D

The frontend will auto-collect models during dev startup and build, so you do
not need to maintain a root `live2d/manifest.json` by hand.

If a model folder contains a `manifest.json`, it will be used as the source of
truth. If not, the importer will fall back to the first `.model3.json` file in
that folder and try to pick a thumbnail from common names such as `icon.jpg`,
`icon.png`, `preview.png`, or `thumb.png`.

Using a sub-manifest is still recommended when you want to customize the model
name, `id`, or default position and scale.

```json
{
  "id": "shinobu",
  "name": "Shinobu",
  "entry": "/assets/live2d/shinobu/shinobu.model3.json",
  "thumbnail": "/assets/live2d/shinobu/preview.png",
  "defaultScale": 0.26,
  "defaultX": 54,
  "defaultY": 76
}
```

`id` and `name` are optional. If omitted, the folder name becomes the model
`id`, and the `entry` filename becomes the display name.

## Backgrounds

`backgrounds/manifest.json`

```json
{
  "backgrounds": [
    {
      "id": "moonlit-room",
      "name": "Moonlit Room",
      "url": "/assets/backgrounds/moonlit-room.webp"
    }
  ]
}
```

## Music

`music/manifest.json`

```json
{
  "tracks": [
    {
      "id": "theme",
      "title": "Theme",
      "artist": "Shinobu",
      "url": "/assets/music/theme.mp3"
    }
  ]
}
```
