import { mkdtemp, mkdir, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { collectLive2DModels } from '../../live2dManifest';
import { mergePetSettings } from './assetManifest';

describe('asset manifest helpers', () => {
  it('merges stored pet settings over defaults', () => {
    expect(mergePetSettings({ opacity: 1, scale: 0.3 }, { opacity: 0.5 })).toEqual({
      opacity: 0.5,
      scale: 0.3,
    });
  });

  it('collects model manifests from child directories', async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'shinobu-live2d-'));
    const live2dRoot = path.join(tempRoot, 'public', 'assets', 'live2d');
    const sealDir = path.join(live2dRoot, 'seal');
    const foxDir = path.join(live2dRoot, 'fox');

    await mkdir(sealDir, { recursive: true });
    await mkdir(foxDir, { recursive: true });
    await mkdir(path.join(live2dRoot, 'notes'), { recursive: true });

    await writeFile(
      path.join(sealDir, 'manifest.json'),
      JSON.stringify({
        entry: 'seal.model3.json',
        thumbnail: 'thumb.png',
        defaultScale: 0.24,
        emotionMapping: {
          happy: { expression: 'sparkle_eyes', motion: 'idle' },
          neutral: { motion: 'idle' },
        },
      }),
      'utf8',
    );
    await writeFile(
      path.join(foxDir, 'manifest.json'),
      JSON.stringify({
        id: 'kitsune',
        name: 'Little Fox',
        entry: '/assets/live2d/fox/fox.model3.json',
      }),
      'utf8',
    );

    await expect(collectLive2DModels(live2dRoot)).resolves.toEqual({
      models: [
        {
          id: 'kitsune',
          name: 'Little Fox',
          entry: '/assets/live2d/fox/fox.model3.json',
        },
        {
          id: 'seal',
          name: 'seal',
          entry: '/assets/live2d/seal/seal.model3.json',
          thumbnail: '/assets/live2d/seal/thumb.png',
          defaultScale: 0.24,
          emotionMapping: {
            happy: { expression: 'sparkle_eyes', motion: 'idle' },
            neutral: { motion: 'idle' },
          },
        },
      ],
    });
  });

  it('infers models from model3 files when a sub-manifest is missing', async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'shinobu-live2d-'));
    const live2dRoot = path.join(tempRoot, 'public', 'assets', 'live2d');
    const akariDir = path.join(live2dRoot, 'akari_vts');

    await mkdir(akariDir, { recursive: true });
    await writeFile(path.join(akariDir, 'akari.model3.json'), '{}', 'utf8');
    await writeFile(path.join(akariDir, 'icon.jpg'), '', 'utf8');
    await writeFile(path.join(akariDir, 'akari.vtube.json'), '{}', 'utf8');

    await expect(collectLive2DModels(live2dRoot)).resolves.toEqual({
      models: [
        {
          id: 'akari_vts',
          name: 'akari',
          entry: '/assets/live2d/akari_vts/akari.model3.json',
          thumbnail: '/assets/live2d/akari_vts/icon.jpg',
        },
      ],
    });
  });
});
