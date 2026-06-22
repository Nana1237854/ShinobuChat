import { useEffect, useRef, useState } from 'react';
import { Gamepad2, ImagePlus, Mic, Plus, Send, Square, X } from 'lucide-react';
import type { ConversationMode, RouteMode } from '../types';
import { getModePlaceholder } from '../modes/ModeSwitch';

const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;

type ComposerProps = {
  disabled: boolean;
  routeMode: RouteMode;
  conversationMode: ConversationMode | null;
  galgameMode: boolean;
  onRouteModeChange: (mode: RouteMode) => void;
  onGalgameModeChange: (enabled: boolean) => void;
  onSubmit: (text: string, imageFile?: File) => void;
  onVoiceInput: (audio: Blob) => Promise<void>;
};

const routeModes: Array<{ value: RouteMode; label: string }> = [
  { value: 'auto', label: '自动' },
  { value: 'chat', label: '聊天' },
  { value: 'agent', label: 'Agent' },
];

const galgameOptions = [
  { label: 'A', text: '我想先继续聊聊这个话题。' },
  { label: 'B', text: '帮我把它整理成可执行步骤。' },
  { label: 'C', text: '先换个角度问我一个关键问题。' },
];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function Composer({
  disabled,
  routeMode,
  conversationMode,
  galgameMode,
  onRouteModeChange,
  onGalgameModeChange,
  onSubmit,
  onVoiceInput,
}: ComposerProps) {
  const [draft, setDraft] = useState('');
  const [recording, setRecording] = useState(false);
  const [recorder, setRecorder] = useState<MediaRecorder | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => () => {
    if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
  }, [imagePreviewUrl]);

  const validateFile = (file: File): string | null => {
    if (!file.type.startsWith('image/')) return '不支持的文件格式，请选择图片';
    if (file.size > MAX_IMAGE_SIZE_BYTES) return `文件过大（${formatFileSize(file.size)}），请压缩或选择小于 ${formatFileSize(MAX_IMAGE_SIZE_BYTES)} 的图片`;
    if (file.size === 0) return '文件为空，请重新选择';
    return null;
  };

  const handleImageSelect = (file: File | null) => {
    if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
    if (!file) {
      setImageFile(null);
      setImagePreviewUrl(null);
      setImageError(null);
      return;
    }
    const error = validateFile(file);
    if (error) {
      setImageFile(null);
      setImagePreviewUrl(null);
      setImageError(error);
      return;
    }
    setImageFile(file);
    setImagePreviewUrl(URL.createObjectURL(file));
    setImageError(null);
  };

  const removeImage = () => {
    handleImageSelect(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const submit = (text = draft) => {
    const trimmed = text.trim();
    if (disabled) return;
    if (!trimmed && !imageFile) return;
    onSubmit(trimmed || '请描述这张图片', imageFile || undefined);
    setDraft('');
    removeImage();
  };

  const toggleRecording = async () => {
    if (recording && recorder) {
      recorder.stop();
      return;
    }
    if (disabled || !navigator.mediaDevices?.getUserMedia) return;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const chunks: Blob[] = [];
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : '';
    const nextRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    nextRecorder.ondataavailable = event => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    nextRecorder.onstop = () => {
      stream.getTracks().forEach(track => track.stop());
      setRecording(false);
      setRecorder(null);
      const audio = new Blob(chunks, { type: nextRecorder.mimeType || 'audio/webm' });
      if (audio.size > 0) {
        onVoiceInput(audio).catch(() => {});
      }
    };
    setRecorder(nextRecorder);
    setRecording(true);
    nextRecorder.start();
  };

  const hasContent = draft.trim().length > 0 || imageFile !== null;

  return (
    <footer className="composer-panel">
      {galgameMode ? (
        <div className="galgame-options" role="group" aria-label="Galgame options">
          {galgameOptions.map(option => (
            <button key={option.label} type="button" disabled={disabled} onClick={() => submit(option.text)}>
              <strong>{option.label}</strong>
              <span>{option.text}</span>
            </button>
          ))}
        </div>
      ) : null}

      {imageError ? (
        <div className="composer-image-error">{imageError}</div>
      ) : null}

      {imagePreviewUrl ? (
        <div className="composer-image-preview">
          <img src={imagePreviewUrl} alt="图片预览" />
          <div className="composer-image-meta">
            <span>{imageFile?.name}</span>
            <small>{imageFile ? formatFileSize(imageFile.size) : ''}</small>
          </div>
          <button
            type="button"
            className="composer-image-remove"
            title="移除图片"
            onClick={removeImage}
          >
            <X size={16} />
          </button>
        </div>
      ) : null}

      <div className="composer-toolbar">
        <div className="segmented-control">
          {routeModes.map(item => (
            <button
              key={item.value}
              type="button"
              className={routeMode === item.value ? 'is-active' : ''}
              onClick={() => onRouteModeChange(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <button
          className={galgameMode ? 'tool-toggle is-active' : 'tool-toggle'}
          type="button"
          title="Galgame options"
          onClick={() => onGalgameModeChange(!galgameMode)}
        >
          <Gamepad2 size={16} />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          style={{ display: 'none' }}
          onChange={event => {
            handleImageSelect(event.target.files?.[0] ?? null);
          }}
        />
        <button
          className={imageFile ? 'tool-toggle is-active' : 'tool-toggle'}
          type="button"
          title="上传图片"
          disabled={disabled}
          onClick={() => fileInputRef.current?.click()}
        >
          <ImagePlus size={16} />
        </button>
        <button
          className={recording ? 'tool-toggle is-active' : 'tool-toggle'}
          type="button"
          title={recording ? 'Stop recording' : 'Voice input'}
          disabled={disabled && !recording}
          onClick={() => {
            toggleRecording().catch(() => {});
          }}
        >
          {recording ? <Square size={15} /> : <Mic size={16} />}
        </button>
      </div>

      <form
        className="composer-form"
        onSubmit={event => {
          event.preventDefault();
          submit();
        }}
      >
        <button className="attach-button" type="button" title="添加内容" disabled={disabled}>
          <Plus size={18} />
        </button>
        <textarea
          value={draft}
          disabled={disabled}
          placeholder={getModePlaceholder(conversationMode)}
          onChange={event => setDraft(event.target.value)}
          onKeyDown={event => {
            if (event.nativeEvent.isComposing) return;
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
        />
        <button className="send-button" type="submit" disabled={disabled || !hasContent} title="Send">
          <Send size={18} />
        </button>
      </form>
      <p className="composer-footnote">由 Shinobu AI 驱动</p>
    </footer>
  );
}
