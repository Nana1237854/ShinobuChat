import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { z } from 'zod';

const subManifestSchema = z.object({
  id: z.string().min(1).optional(),
  name: z.string().min(1).optional(),
  entry: z.string().min(1),
  thumbnail: z.string().min(1).optional(),
  defaultScale: z.number().optional(),
  defaultX: z.number().optional(),
  defaultY: z.number().optional(),
});

export const AUTO_LIVE2D_MANIFEST_PATH = '/assets/live2d/manifest.auto.json';
export const AUTO_LIVE2D_MANIFEST_FILE = 'assets/live2d/manifest.auto.json';

type Live2DManifestModel = z.infer<typeof subManifestSchema> & {
  id: string;
  name: string;
};

export type Live2DManifest = {
  models: Live2DManifestModel[];
};

const thumbnailCandidates = [
  'preview.png',
  'preview.jpg',
  'preview.jpeg',
  'preview.webp',
  'thumbnail.png',
  'thumbnail.jpg',
  'thumbnail.jpeg',
  'thumbnail.webp',
  'thumb.png',
  'thumb.jpg',
  'thumb.jpeg',
  'thumb.webp',
  'icon.png',
  'icon.jpg',
  'icon.jpeg',
  'icon.webp',
];

function stripBom(contents: string): string {
  return contents.charCodeAt(0) === 0xfeff ? contents.slice(1) : contents;
}

function trimModel3Extension(filename: string): string {
  return filename.replace(/\.model3\.json$/i, '').replace(/\.json$/i, '');
}

function toPublicAssetPath(publicDir: string, filePath: string): string {
  const relativePath = path.relative(publicDir, filePath);
  return `/${relativePath.split(path.sep).join('/')}`;
}

function resolveManifestAssetPath(publicDir: string, modelDir: string, assetPath: string): string {
  if (assetPath.startsWith('/')) {
    return assetPath;
  }
  return toPublicAssetPath(publicDir, path.resolve(modelDir, assetPath));
}

async function readSubManifest(manifestPath: string) {
  const raw = await readFile(manifestPath, 'utf8');
  return subManifestSchema.parse(JSON.parse(stripBom(raw)));
}

function createModelRecord(
  publicDir: string,
  modelDir: string,
  folderName: string,
  manifest: z.infer<typeof subManifestSchema>,
): Live2DManifestModel {
  const entryFileName = path.basename(manifest.entry);
  const defaultName = trimModel3Extension(entryFileName) || folderName;

  return {
    ...manifest,
    id: manifest.id ?? folderName,
    name: manifest.name ?? defaultName,
    entry: resolveManifestAssetPath(publicDir, modelDir, manifest.entry),
    thumbnail: manifest.thumbnail
      ? resolveManifestAssetPath(publicDir, modelDir, manifest.thumbnail)
      : undefined,
  };
}

async function inferModelManifest(modelDir: string) {
  const files = await readdir(modelDir, { withFileTypes: true });
  const fileNames = files
    .filter(file => file.isFile())
    .map(file => file.name);
  const entryFile = fileNames
    .filter(fileName => /\.model3\.json$/i.test(fileName))
    .sort((left, right) => left.localeCompare(right))[0];

  if (!entryFile) return null;

  const thumbnail = thumbnailCandidates.find(candidate =>
    fileNames.some(fileName => fileName.toLowerCase() === candidate),
  );

  return subManifestSchema.parse({
    entry: entryFile,
    thumbnail,
  });
}

export async function collectLive2DModels(live2dDir: string): Promise<Live2DManifest> {
  const publicDir = path.resolve(live2dDir, '..', '..');
  const entries = await readdir(live2dDir, { withFileTypes: true });
  const models: Live2DManifestModel[] = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;

    const modelDir = path.join(live2dDir, entry.name);
    const manifestPath = path.join(modelDir, 'manifest.json');

    try {
      const manifest = await readSubManifest(manifestPath);
      models.push(createModelRecord(publicDir, modelDir, entry.name, manifest));
    } catch (error) {
      const isMissingManifest =
        error instanceof Error && 'code' in error && (error as NodeJS.ErrnoException).code === 'ENOENT';
      if (isMissingManifest) {
        const inferredManifest = await inferModelManifest(modelDir);
        if (!inferredManifest) continue;
        models.push(createModelRecord(publicDir, modelDir, entry.name, inferredManifest));
        continue;
      }
      throw new Error(`Failed to read Live2D manifest in ${modelDir}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  models.sort((left, right) => left.name.localeCompare(right.name, 'zh-Hans-CN'));
  return { models };
}
