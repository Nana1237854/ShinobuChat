import react from '@vitejs/plugin-react';
import path from 'node:path';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';
import {
  AUTO_LIVE2D_MANIFEST_FILE,
  AUTO_LIVE2D_MANIFEST_PATH,
  collectLive2DModels,
} from './live2dManifest';

function live2dManifestPlugin(): Plugin {
  let projectRoot = process.cwd();

  const live2dRoot = () => path.join(projectRoot, 'public', 'assets', 'live2d');
  const loadManifest = () => collectLive2DModels(live2dRoot());
  const isLive2DAsset = (filePath: string) => {
    const root = live2dRoot();
    const resolvedPath = path.resolve(filePath);
    return resolvedPath === root || resolvedPath.startsWith(`${root}${path.sep}`);
  };

  return {
    name: 'live2d-manifest-plugin',
    configResolved(config) {
      projectRoot = config.root;
    },
    configureServer(server) {
      const notifyManifestChanged = (filePath: string) => {
        if (!isLive2DAsset(filePath)) return;
        server.ws.send({
          type: 'custom',
          event: 'live2d-assets:refresh',
        });
      };

      server.watcher.add(live2dRoot());
      server.watcher.on('add', notifyManifestChanged);
      server.watcher.on('change', notifyManifestChanged);
      server.watcher.on('unlink', notifyManifestChanged);
      server.watcher.on('addDir', notifyManifestChanged);
      server.watcher.on('unlinkDir', notifyManifestChanged);

      server.middlewares.use(async (request, response, next) => {
        const requestPath = request.url?.split('?')[0];
        if (requestPath !== AUTO_LIVE2D_MANIFEST_PATH) {
          next();
          return;
        }

        try {
          const manifest = await loadManifest();
          response.setHeader('Content-Type', 'application/json; charset=utf-8');
          response.end(JSON.stringify(manifest, null, 2));
        } catch (error) {
          response.statusCode = 500;
          response.setHeader('Content-Type', 'application/json; charset=utf-8');
          response.end(JSON.stringify({
            error: error instanceof Error ? error.message : 'Failed to generate Live2D manifest',
          }));
        }
      });
    },
    async generateBundle() {
      const manifest = await loadManifest();
      this.emitFile({
        type: 'asset',
        fileName: AUTO_LIVE2D_MANIFEST_FILE,
        source: JSON.stringify(manifest, null, 2),
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), live2dManifestPlugin()],
  server: {
    host: '0.0.0.0',
    port: 5175,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
});
