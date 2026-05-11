import { useEffect, useRef, useState } from 'react';
import type { AvatarTool, Live2DModelItem, PetSettings } from '../types';
import { clamp } from './settings';

type Live2DStageProps = {
  model?: Live2DModelItem;
  settings: PetSettings;
  activeEmotion?: string | null;
  activeTool: AvatarTool | null;
  onSettingsChange: (settings: PetSettings) => void;
  onInteract: () => void;
};

type LoadedRuntime = {
  app: {
    destroy: (removeView?: boolean, options?: { children?: boolean; texture?: boolean; baseTexture?: boolean }) => void;
    view: HTMLCanvasElement;
    stage: { addChild: (child: unknown) => void };
    renderer: { resize: (width: number, height: number) => void };
  };
  modelObject?: {
    destroy?: () => void;
    scale?: { set: (value: number) => void };
    anchor?: { set: (x: number, y: number) => void };
    position?: { set: (x: number, y: number) => void };
    expression?: (id?: number | string) => Promise<boolean>;
    motion?: (group: string, index?: number) => Promise<boolean>;
    alpha?: number;
  };
};

let cubismCorePromise: Promise<void> | null = null;

function ensureCubism4Core(): Promise<void> {
  if ((window as Window & { Live2DCubismCore?: unknown }).Live2DCubismCore) {
    return Promise.resolve();
  }
  if (cubismCorePromise) return cubismCorePromise;

  cubismCorePromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = '/vendor/live2dcubismcore.min.js';
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Failed to load Cubism 4 core runtime'));
    document.head.appendChild(script);
  });

  return cubismCorePromise;
}

function normalizeEmotion(emotion?: string | null): string {
  return (emotion || 'neutral').trim().toLowerCase().replace(/\s+/g, '_') || 'neutral';
}

function parseMotionRef(motion: string): { group: string; index?: number } {
  const bracketMatch = /^(.+)\[(\d+)\]$/.exec(motion);
  if (bracketMatch) {
    return { group: bracketMatch[1], index: Number(bracketMatch[2]) };
  }

  const colonMatch = /^(.+):(\d+)$/.exec(motion);
  if (colonMatch) {
    return { group: colonMatch[1], index: Number(colonMatch[2]) };
  }

  return { group: motion };
}

function applyLive2DEmotion(runtime: LoadedRuntime | null, model: Live2DModelItem | undefined, emotion?: string | null) {
  const mapping = model?.emotionMapping;
  const modelObject = runtime?.modelObject;
  if (!mapping || !modelObject) return;

  const normalized = normalizeEmotion(emotion);
  const mappedEmotion = mapping[normalized] ?? mapping.neutral;
  if (!mappedEmotion) return;

  if (mappedEmotion.expression && modelObject.expression) {
    modelObject.expression(mappedEmotion.expression).catch(error => {
      console.warn(`Failed to apply Live2D expression "${mappedEmotion.expression}"`, error);
    });
  }

  if (mappedEmotion.motion && modelObject.motion) {
    const { group, index } = parseMotionRef(mappedEmotion.motion);
    modelObject.motion(group, index).catch(error => {
      console.warn(`Failed to apply Live2D motion "${mappedEmotion.motion}"`, error);
    });
  }
}

async function createLive2DRuntime(container: HTMLDivElement, model: Live2DModelItem, settings: PetSettings): Promise<LoadedRuntime> {
  const PIXI = await import('pixi.js');
  await ensureCubism4Core();
  Object.assign(window, { PIXI });
  const live2d = await import('pixi-live2d-display/cubism4');
  const app = new PIXI.Application({
    resizeTo: container,
    backgroundAlpha: 0,
    antialias: true,
    autoDensity: true,
  });
  container.appendChild(app.view as HTMLCanvasElement);

  const Live2DModel = (live2d as unknown as {
    Live2DModel: {
      from: (entry: string) => Promise<LoadedRuntime['modelObject']>;
      registerTicker?: (ticker: typeof PIXI.Ticker) => void;
    };
  }).Live2DModel;
  Live2DModel.registerTicker?.(PIXI.Ticker);
  const modelObject = await Live2DModel.from(model.entry);
  modelObject?.anchor?.set(0.5, 1);
  modelObject?.scale?.set(settings.scale);
  if (modelObject) modelObject.alpha = settings.opacity;
  modelObject?.position?.set(container.clientWidth * settings.x / 100, container.clientHeight * settings.y / 100);
  if (!modelObject) {
    throw new Error('Live2D model was not created');
  }
  app.stage.addChild(modelObject as never);
  return { app: app as unknown as LoadedRuntime['app'], modelObject };
}

export function Live2DStage({
  model,
  settings,
  activeEmotion,
  activeTool,
  onSettingsChange,
  onInteract,
}: Live2DStageProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<LoadedRuntime | null>(null);
  const emotionRef = useRef<string | null | undefined>(activeEmotion);
  const dragRef = useRef<{ pointerId: number; startX: number; startY: number; originX: number; originY: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !model) {
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    runtimeRef.current?.app.destroy(true, { children: true, texture: true, baseTexture: true });
    runtimeRef.current = null;
    container.replaceChildren();

    createLive2DRuntime(container, model, settings)
      .then(runtime => {
        if (cancelled) {
          runtime.app.destroy(true, { children: true, texture: true, baseTexture: true });
          return;
        }
        runtimeRef.current = runtime;
        applyLive2DEmotion(runtime, model, emotionRef.current);
      })
      .catch(nextError => {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : 'Live2D runtime failed to load');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      runtimeRef.current?.app.destroy(true, { children: true, texture: true, baseTexture: true });
      runtimeRef.current = null;
      container.replaceChildren();
    };
  }, [model?.entry]);

  useEffect(() => {
    emotionRef.current = activeEmotion;
    applyLive2DEmotion(runtimeRef.current, model, activeEmotion);
  }, [activeEmotion, model?.emotionMapping]);

  useEffect(() => {
    const container = containerRef.current;
    const runtime = runtimeRef.current;
    if (!container || !runtime?.modelObject) return;
    runtime.modelObject.scale?.set(settings.scale);
    runtime.modelObject.position?.set(container.clientWidth * settings.x / 100, container.clientHeight * settings.y / 100);
    runtime.modelObject.alpha = settings.opacity;
  }, [settings.opacity, settings.scale, settings.x, settings.y]);

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: settings.x,
      originY: settings.y,
    };
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    const container = containerRef.current;
    if (!drag || !container || drag.pointerId !== event.pointerId) return;
    const dx = (event.clientX - drag.startX) / Math.max(container.clientWidth, 1) * 100;
    const dy = (event.clientY - drag.startY) / Math.max(container.clientHeight, 1) * 100;
    onSettingsChange({
      ...settings,
      x: clamp(drag.originX + dx, -20, 120),
      y: clamp(drag.originY + dy, 0, 120),
    });
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId === event.pointerId) {
      dragRef.current = null;
    }
  };

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    const nextScale = settings.scale + (event.deltaY > 0 ? -0.03 : 0.03);
    onSettingsChange({ ...settings, scale: clamp(nextScale, 0.12, 1.2) });
  };

  return (
    <div
      className="live2d-stage"
      data-tool={activeTool || ''}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      onDoubleClick={onInteract}
      onWheel={handleWheel}
    >
      <div className="live2d-canvas-host" ref={containerRef} style={{ opacity: settings.opacity }} />
      {!model ? (
        <div className="live2d-placeholder">
          <strong>Live2D model folder is ready</strong>
          <span>Put models in public/assets/live2d and register them in manifest.json.</span>
        </div>
      ) : null}
      {loading ? <div className="live2d-status">Loading {model?.name}...</div> : null}
      {error ? (
        <div className="live2d-placeholder is-error">
          <strong>Live2D fallback</strong>
          <span>{error}</span>
        </div>
      ) : null}
    </div>
  );
}
