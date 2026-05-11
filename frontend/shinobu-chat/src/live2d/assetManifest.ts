import { z } from 'zod';
import type { BackgroundItem, Live2DModelItem, MusicTrack } from '../types';

const AUTO_LIVE2D_MANIFEST_PATH = '/assets/live2d/manifest.auto.json';

const live2dManifestSchema = z.object({
  models: z.array(z.object({
    id: z.string().min(1),
    name: z.string().min(1),
    entry: z.string().min(1),
    thumbnail: z.string().optional(),
    defaultScale: z.number().optional(),
    defaultX: z.number().optional(),
    defaultY: z.number().optional(),
    emotionMapping: z.record(z.object({
      expression: z.string().min(1).optional(),
      motion: z.string().min(1).optional(),
    })).optional(),
  })),
});

const backgroundsManifestSchema = z.object({
  backgrounds: z.array(z.object({
    id: z.string().min(1),
    name: z.string().min(1),
    url: z.string().optional(),
    gradient: z.string().optional(),
  })),
});

const musicManifestSchema = z.object({
  tracks: z.array(z.object({
    id: z.string().min(1),
    title: z.string().min(1),
    artist: z.string().optional(),
    url: z.string().min(1),
  })),
});

async function fetchJson<T>(url: string, fallback: T, parser: (value: unknown) => T): Promise<T> {
  try {
    const response = await fetch(url, { cache: 'no-cache' });
    if (!response.ok) return fallback;
    return parser(await response.json());
  } catch {
    return fallback;
  }
}

async function fetchOptionalJson<T>(url: string, parser: (value: unknown) => T): Promise<T | null> {
  try {
    const response = await fetch(url, { cache: 'no-cache' });
    if (!response.ok) return null;
    return parser(await response.json());
  } catch {
    return null;
  }
}

export function mergePetSettings<T extends Record<string, unknown>>(defaults: T, stored: unknown): T {
  if (!stored || typeof stored !== 'object') return defaults;
  return { ...defaults, ...stored };
}

export async function loadLive2DModels(): Promise<Live2DModelItem[]> {
  const generatedManifest = await fetchOptionalJson(
    AUTO_LIVE2D_MANIFEST_PATH,
    value => live2dManifestSchema.parse(value),
  );
  if (generatedManifest) return generatedManifest.models;

  const legacyManifest = await fetchJson(
    '/assets/live2d/manifest.json',
    { models: [] as Live2DModelItem[] },
    value => live2dManifestSchema.parse(value),
  );
  return legacyManifest.models;
}

export async function loadBackgrounds(): Promise<BackgroundItem[]> {
  const manifest = await fetchJson(
    '/assets/backgrounds/manifest.json',
    {
      backgrounds: [{
        id: 'fallback',
        name: 'Fallback',
        gradient: 'linear-gradient(135deg, #dceefe, #f9e6ed)',
      }],
    },
    value => backgroundsManifestSchema.parse(value),
  );
  return manifest.backgrounds;
}

export async function loadMusicTracks(): Promise<MusicTrack[]> {
  const manifest = await fetchJson(
    '/assets/music/manifest.json',
    { tracks: [] as MusicTrack[] },
    value => musicManifestSchema.parse(value),
  );
  return manifest.tracks;
}
