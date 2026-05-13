import { useState } from 'react';
import { Gamepad2, Mic, Plus, Send, Square } from 'lucide-react';
import type { RouteMode } from '../types';

type ComposerProps = {
  disabled: boolean;
  routeMode: RouteMode;
  galgameMode: boolean;
  onRouteModeChange: (mode: RouteMode) => void;
  onGalgameModeChange: (enabled: boolean) => void;
  onSubmit: (text: string) => void;
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

export function Composer({
  disabled,
  routeMode,
  galgameMode,
  onRouteModeChange,
  onGalgameModeChange,
  onSubmit,
  onVoiceInput,
}: ComposerProps) {
  const [draft, setDraft] = useState('');
  const [recording, setRecording] = useState(false);
  const [recorder, setRecorder] = useState<MediaRecorder | null>(null);

  const submit = (text = draft) => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setDraft('');
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
          placeholder="输入消息..."
          onChange={event => setDraft(event.target.value)}
          onKeyDown={event => {
            if (event.nativeEvent.isComposing) return;
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
        />
        <button className="send-button" type="submit" disabled={disabled || !draft.trim()} title="Send">
          <Send size={18} />
        </button>
      </form>
      <p className="composer-footnote">由 Shinobu AI 驱动</p>
    </footer>
  );
}
