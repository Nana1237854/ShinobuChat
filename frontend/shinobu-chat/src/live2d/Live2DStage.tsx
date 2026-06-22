import { useCallback, useEffect, useRef, useState } from 'react';
import { Palette, SlidersHorizontal, UserRoundCog, X } from 'lucide-react';
import type { AvatarTool, ConversationMode, Live2DHitArea, Live2DModelItem, PetSettings } from '../types';
import { clamp } from './settings';
import { LIP_SYNC_IDS } from './lipSync';

type Live2DStageProps = {
  model?: Live2DModelItem;
  settings: PetSettings;
  activeEmotion?: string | null;
  activeTool: AvatarTool | null;
  conversationMode?: ConversationMode | null;
  onSettingsChange: (settings: PetSettings) => void;
  onInteract: () => void;
  onLipSyncReady?: (setter: (value: number) => void) => void;
  onOpenSettings?: (tab?: string) => void;
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
    internalModel?: {
      coreModel?: {
        setParameterValueById?: (id: string, value: number) => void;
      };
    };
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
  conversationMode,
  onSettingsChange,
  onInteract,
  onLipSyncReady,
  onOpenSettings,
}: Live2DStageProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<LoadedRuntime | null>(null);
  const emotionRef = useRef<string | null | undefined>(activeEmotion);
  const onLipSyncReadyRef = useRef(onLipSyncReady);
  onLipSyncReadyRef.current = onLipSyncReady;
  const dragRef = useRef<{ pointerId: number; startX: number; startY: number; originX: number; originY: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const prevEntryRef = useRef<string | undefined>();

  // ── Interaction state ──
  const [bubble, setBubble] = useState<{ text: string; x: number; y: number } | null>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);

  const lastClickTimeRef = useRef(0);
  const longPressTimerRef = useRef<number | null>(null);
  const clickStartPosRef = useRef<{ x: number; y: number } | null>(null);
  const tempEmotionTimerRef = useRef<number | null>(null);
  const longPressTriggeredRef = useRef(false);
  const interactionArmedRef = useRef(false);
  const bubbleIdRef = useRef(0);

  const clearLongPressTimer = useCallback(() => {
    if (longPressTimerRef.current !== null) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  }, []);

  const clearTempEmotion = useCallback(() => {
    if (tempEmotionTimerRef.current !== null) {
      clearTimeout(tempEmotionTimerRef.current);
      tempEmotionTimerRef.current = null;
    }
  }, []);

  const detectHitArea = useCallback((clientX: number, clientY: number, stageRect: DOMRect): Live2DHitArea => {
    const relX = (clientX - stageRect.left) / (stageRect.width || 1);
    const relY = (clientY - stageRect.top) / (stageRect.height || 1);

    const modelCenterX = settings.x / 100;
    const modelBottom = settings.y / 100;
    const modelHeight = settings.scale * 1.2;
    const modelWidth = modelHeight * 0.6;

    const modelLeft = modelCenterX - modelWidth / 2;
    const modelRight = modelCenterX + modelWidth / 2;
    const modelTop = modelBottom - modelHeight;

    if (relX >= modelLeft && relX <= modelRight && relY >= modelTop && relY <= modelBottom) {
      const vertPos = (relY - modelTop) / (modelHeight || 0.001);
      if (vertPos < 0.35) return 'head';
      if (vertPos < 0.75) return 'body';
      return 'hand';
    }

    if (relX >= modelLeft - 0.05 && relX <= modelRight + 0.05 && relY >= modelTop && relY <= modelBottom) {
      return 'hand';
    }

    return 'unknown';
  }, [settings.scale, settings.x, settings.y]);

  const closeContextMenu = useCallback(() => {
    setContextMenu(null);
  }, []);

  const emitBubble = useCallback((text: string, x: number, y: number) => {
    bubbleIdRef.current += 1;
    const currentId = bubbleIdRef.current;
    setBubble({ text, x, y });
    window.setTimeout(() => {
      if (bubbleIdRef.current === currentId) {
        setBubble(null);
      }
    }, 1500);
  }, []);

  const handleClickFeedback = useCallback((hitArea: Live2DHitArea, clientX: number, clientY: number, stageRect: DOMRect) => {
    // Focus mode: only respond to head clicks, suppress body/hand interactions
    if (conversationMode === 'focus' && hitArea !== 'head') {
      return;
    }

    const x = clientX - stageRect.left;
    const y = clientY - stageRect.top;

    switch (hitArea) {
      case 'head': {
        emitBubble('嗯？', x, y);
        const runtime = runtimeRef.current;
        if (runtime && model?.emotionMapping) {
          const prevEmotion = emotionRef.current;
          const emotionToTry = model.emotionMapping.happy
            ? 'happy'
            : model.emotionMapping.shy
              ? 'shy'
              : model.emotionMapping.neutral
                ? 'neutral'
                : null;
          if (emotionToTry) {
            applyLive2DEmotion(runtime, model, emotionToTry);
            clearTempEmotion();
            tempEmotionTimerRef.current = window.setTimeout(() => {
              applyLive2DEmotion(runtime, model, prevEmotion);
            }, 2000);
          }
        }
        break;
      }
      case 'body': {
        emitBubble('…', x, y);
        break;
      }
      case 'hand': {
        emitBubble('嗨~', x, y);
        break;
      }
      default:
        break;
    }
  }, [emitBubble, model, clearTempEmotion, conversationMode]);

  // ── Lifecycle ──

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !model) {
      setError(null);
      return;
    }

    // Guard: skip if entry hasn't changed (prevents React StrictMode / HMR re-triggers)
    if (prevEntryRef.current === model.entry) return;
    prevEntryRef.current = model.entry;

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
        const core = runtime.modelObject?.internalModel?.coreModel;
        if (onLipSyncReadyRef.current && core?.setParameterValueById) {
          for (const id of LIP_SYNC_IDS) {
            try {
              core.setParameterValueById(id, 0);
            } catch (_) {}
          }
          onLipSyncReadyRef.current?.((value: number) => {
            for (const id of LIP_SYNC_IDS) {
              try {
                core.setParameterValueById?.(id, value);
              } catch (_) {}
            }
          });
        }
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
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

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const syncRuntimeSize = () => {
      const runtime = runtimeRef.current;
      if (!runtime?.modelObject) return;
      const width = Math.max(container.clientWidth, 1);
      const height = Math.max(container.clientHeight, 1);
      runtime.app.renderer.resize(width, height);
      runtime.modelObject.position?.set(width * settings.x / 100, height * settings.y / 100);
    };

    syncRuntimeSize();
    const observer = new ResizeObserver(syncRuntimeSize);
    observer.observe(container);
    return () => observer.disconnect();
  }, [settings.x, settings.y, model?.entry]);

  // ── Timer cleanup on unmount ──

  useEffect(() => {
    return () => {
      clearLongPressTimer();
      clearTempEmotion();
    };
  }, [clearLongPressTimer, clearTempEmotion]);

  // ── Pointer event handlers ──

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: settings.x,
      originY: settings.y,
    };

    // Only arm interaction tracking when a model is loaded
    if (!model) return;

    clickStartPosRef.current = { x: event.clientX, y: event.clientY };
    longPressTriggeredRef.current = false;
    interactionArmedRef.current = true;

    clearLongPressTimer();
    longPressTimerRef.current = window.setTimeout(() => {
      if (!interactionArmedRef.current) return;
      longPressTriggeredRef.current = true;
      const stageEl = stageRef.current;
      if (!stageEl) return;
      const rect = stageEl.getBoundingClientRect();
      setContextMenu({
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      });
    }, 600);
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

    // Cancel long-press if pointer moved beyond threshold
    if (clickStartPosRef.current) {
      const moveDistance = Math.hypot(
        event.clientX - clickStartPosRef.current.x,
        event.clientY - clickStartPosRef.current.y,
      );
      if (moveDistance > 10) {
        clearLongPressTimer();
        interactionArmedRef.current = false;
      }
    }
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId === event.pointerId) {
      dragRef.current = null;
    }

    clearLongPressTimer();

    // Click detection: must be armed, not a long-press, and model loaded
    if (interactionArmedRef.current && !longPressTriggeredRef.current && model) {
      const startPos = clickStartPosRef.current;
      if (startPos) {
        const moveDistance = Math.hypot(
          event.clientX - startPos.x,
          event.clientY - startPos.y,
        );
        // Only treat as click if pointer didn't move far (not a drag)
        if (moveDistance <= 5) {
          const now = Date.now();
          if (now - lastClickTimeRef.current >= 500) {
            lastClickTimeRef.current = now;
            const stageEl = stageRef.current;
            if (stageEl) {
              const rect = stageEl.getBoundingClientRect();
              const hitArea = detectHitArea(event.clientX, event.clientY, rect);
              if (hitArea !== 'unknown') {
                handleClickFeedback(hitArea, event.clientX, event.clientY, rect);
              }
            }
          }
        }
      }
    }

    interactionArmedRef.current = false;
    clickStartPosRef.current = null;
  };

  const handlePointerCancel = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId === event.pointerId) {
      dragRef.current = null;
    }
    clearLongPressTimer();
    interactionArmedRef.current = false;
    clickStartPosRef.current = null;
  };

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    const nextScale = settings.scale + (event.deltaY > 0 ? -0.03 : 0.03);
    onSettingsChange({ ...settings, scale: clamp(nextScale, 0.12, 1.2) });
  };

  // ── Context menu actions ──

  const handleContextMenuAction = useCallback((tab: string) => {
    onOpenSettings?.(tab);
    closeContextMenu();
  }, [onOpenSettings, closeContextMenu]);

  const handleContextMenuClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
  }, []);

  return (
    <div
      ref={stageRef}
      className="live2d-stage"
      data-tool={activeTool || ''}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
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

      {/* Interaction bubble */}
      {bubble ? (
        <div
          className={['live2d-interaction-bubble', conversationMode === 'night' ? 'is-night-mode' : ''].filter(Boolean).join(' ')}
          style={{ left: bubble.x, top: bubble.y - 36 }}
        >
          {bubble.text}
        </div>
      ) : null}

      {/* Context menu */}
      {contextMenu ? (
        <>
          <div
            className="live2d-context-menu-backdrop"
            onClick={closeContextMenu}
            onContextMenu={e => e.preventDefault()}
          />
          <div
            className="live2d-context-menu"
            style={{ left: contextMenu.x, top: contextMenu.y }}
            onClick={handleContextMenuClick}
            onMouseDown={handleContextMenuClick}
          >
            <button
              type="button"
              className="live2d-context-menu-item"
              onClick={() => handleContextMenuAction('persona')}
            >
              <UserRoundCog size={14} />
              <span>角色设置</span>
            </button>
            <button
              type="button"
              className="live2d-context-menu-item"
              onClick={() => handleContextMenuAction('mode')}
            >
              <SlidersHorizontal size={14} />
              <span>情景模式</span>
            </button>
            <button
              type="button"
              className="live2d-context-menu-item"
              onClick={() => handleContextMenuAction('appearance')}
            >
              <Palette size={14} />
              <span>外观设置</span>
            </button>
            <div className="live2d-context-menu-divider" />
            <button
              type="button"
              className="live2d-context-menu-item"
              onClick={closeContextMenu}
            >
              <X size={14} />
              <span>关闭</span>
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}
