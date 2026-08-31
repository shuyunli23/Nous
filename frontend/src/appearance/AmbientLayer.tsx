import { PlayerBackground } from './PlayerBackgrounds';
import { useAmbientEffect } from './AppearanceProvider';
import type { Surface } from './types';

export default function AmbientLayer({ surface }: { surface: Surface }) {
  const id = useAmbientEffect(surface);
  if (id === 'none') return null;
  return (
    <div className={`ambient ambient--${surface} ambient--harmony`} aria-hidden="true">
      <PlayerBackground backgroundId={id} isPlaying />
      {surface === 'sidebar' ? <div className="ambient__veil" /> : null}
    </div>
  );
}
