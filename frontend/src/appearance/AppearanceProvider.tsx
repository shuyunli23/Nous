import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import {
  APPEARANCE_EVENT,
  effectFor,
  loadPrefs,
  msUntilNextPeriod,
  periodAt,
  savePrefs,
} from './store';
import { applyUiFonts } from './fonts';
import type { AppearancePrefs, EffectId, Period, Surface } from './types';

interface AppearanceContextValue {
  prefs: AppearancePrefs;
  period: Period;
  setPrefs: (next: AppearancePrefs) => void;
  patchPrefs: (patch: Partial<AppearancePrefs>) => void;
  effectFor: (surface: Surface) => EffectId;
}

const AppearanceContext = createContext<AppearanceContextValue | null>(null);

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefsState] = useState<AppearancePrefs>(loadPrefs);
  const [period, setPeriod] = useState<Period>(periodAt);

  useEffect(() => {
    const sync = () => setPrefsState(loadPrefs());
    window.addEventListener(APPEARANCE_EVENT, sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(APPEARANCE_EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  useEffect(() => {
    let timer = 0;
    const tick = () => {
      setPeriod(periodAt());
      timer = window.setTimeout(tick, Math.min(msUntilNextPeriod(), 60_000));
    };
    tick();
    const onVis = () => {
      if (document.visibilityState === 'visible') setPeriod(periodAt());
    };
    document.addEventListener('visibilitychange', onVis);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVis);
    };
  }, []);

  useLayoutEffect(() => {
    applyUiFonts(prefs.latinFont, prefs.cjkFont);
  }, [prefs.latinFont, prefs.cjkFont]);

  const setPrefs = useCallback((next: AppearancePrefs) => {
    setPrefsState(next);
    savePrefs(next);
  }, []);

  const patchPrefs = useCallback((patch: Partial<AppearancePrefs>) => {
    setPrefsState((prev) => {
      const next = { ...prev, ...patch };
      savePrefs(next);
      return next;
    });
  }, []);

  const value = useMemo<AppearanceContextValue>(
    () => ({
      prefs,
      period,
      setPrefs,
      patchPrefs,
      effectFor: (surface) => effectFor(prefs, surface, period),
    }),
    [prefs, period, setPrefs, patchPrefs],
  );

  return (
    <AppearanceContext.Provider value={value}>{children}</AppearanceContext.Provider>
  );
}

export function useAppearance(): AppearanceContextValue {
  const ctx = useContext(AppearanceContext);
  if (!ctx) {
    throw new Error('useAppearance must be used inside AppearanceProvider');
  }
  return ctx;
}

export function useAmbientEffect(surface: Surface): EffectId {
  return useAppearance().effectFor(surface);
}
