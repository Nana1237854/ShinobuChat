import type { PetSettings } from '../types';
import { mergePetSettings } from './assetManifest';

const SETTINGS_KEY = 'shinobu-pet-settings';

export const defaultPetSettings: PetSettings = {
  modelId: 'mao_pro_en',
  backgroundId: 'gradient-dusk',
  opacity: 1,
  reminderMode: 'toast',
  scale: 0.32,
  x: 52,
  y: 72,
};

export function loadPetSettings(): PetSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return defaultPetSettings;
    const merged = mergePetSettings(defaultPetSettings, JSON.parse(raw));
    return {
      ...merged,
      opacity: clamp(Number(merged.opacity), 0.25, 1),
      scale: clamp(Number(merged.scale), 0.12, 1.2),
      x: clamp(Number(merged.x), -20, 120),
      y: clamp(Number(merged.y), 0, 120),
    };
  } catch {
    return defaultPetSettings;
  }
}

export function savePetSettings(settings: PetSettings): void {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

export function clamp(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}
