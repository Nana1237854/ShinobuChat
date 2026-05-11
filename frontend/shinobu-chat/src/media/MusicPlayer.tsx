import { useEffect, useRef, useState } from 'react';
import { Pause, Play, Repeat, SkipBack, SkipForward, Volume2 } from 'lucide-react';
import type { MusicTrack } from '../types';

type MusicPlayerProps = {
  tracks: MusicTrack[];
};

export function MusicPlayer({ tracks }: MusicPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loop, setLoop] = useState(true);
  const [volume, setVolume] = useState(0.55);
  const track = tracks[index];

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.volume = volume;
    audio.loop = loop;
  }, [volume, loop]);

  useEffect(() => {
    if (!playing) return;
    audioRef.current?.play().catch(() => setPlaying(false));
  }, [index, playing]);

  const move = (direction: 1 | -1) => {
    if (tracks.length === 0) return;
    setIndex(current => (current + direction + tracks.length) % tracks.length);
  };

  const toggle = () => {
    const audio = audioRef.current;
    if (!audio || !track) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
    } else {
      audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    }
  };

  return (
    <section className="music-player" aria-label="Music player">
      <audio ref={audioRef} src={track?.url} onEnded={() => move(1)} />
      <div className="music-meta">
        <strong>{track?.title || 'No track'}</strong>
        <span>{track?.artist || 'Add music in assets/music'}</span>
      </div>
      <div className="music-controls">
        <button type="button" disabled={tracks.length === 0} title="Previous" onClick={() => move(-1)}><SkipBack size={15} /></button>
        <button type="button" disabled={!track} title="Play" onClick={toggle}>{playing ? <Pause size={15} /> : <Play size={15} />}</button>
        <button type="button" disabled={tracks.length === 0} title="Next" onClick={() => move(1)}><SkipForward size={15} /></button>
        <button className={loop ? 'is-active' : ''} type="button" title="Loop" onClick={() => setLoop(value => !value)}><Repeat size={15} /></button>
        <label className="volume-control" title="Volume">
          <Volume2 size={15} />
          <input type="range" min="0" max="1" step="0.01" value={volume} onChange={event => setVolume(Number(event.target.value))} />
        </label>
      </div>
    </section>
  );
}
