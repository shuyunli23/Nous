import {
  EFFECT_IDS,
  PERIODS,
  type AppearancePrefs,
  type EffectId,
  type Period,
  type Surface,
  type SurfaceEffects,
} from './types';
import { CJK_FONT_IDS, LATIN_FONT_IDS, type CjkFontId, type LatinFontId } from './fonts';
import { DEFAULT_WORKSPACE, parseWorkspace } from './workspace';

export const APPEARANCE_KEY = 'nous.appearance';
export const APPEARANCE_EVENT = 'nous-appearance';

const CALM: SurfaceEffects = { graph: 'orbs', sidebar: 'orbs' };

export const DEFAULT_PREFS: AppearancePrefs = {
  mode: 'schedule',
  manual: { graph: 'orbs', sidebar: 'orbs' },
  schedule: {
    morning: { graph: 'orbs', sidebar: 'orbs' },
    noon: { graph: 'aurora', sidebar: 'aurora' },
    evening: { graph: 'sunset', sidebar: 'sunset' },
    night: { graph: 'starfield', sidebar: 'starfield' },
  },
  cjkFont: 'system',
  latinFont: 'jakarta',
  workspace: DEFAULT_WORKSPACE,
};

function isEffect(value: unknown): value is EffectId {
  return typeof value === 'string' && (EFFECT_IDS as readonly string[]).includes(value);
}

function readSurface(raw: unknown, fallback: SurfaceEffects): SurfaceEffects {
  if (!raw || typeof raw !== 'object') return fallback;
  const rec = raw as Record<string, unknown>;
  return {
    graph: isEffect(rec.graph) ? rec.graph : fallback.graph,
    sidebar: isEffect(rec.sidebar) ? rec.sidebar : fallback.sidebar,
  };
}

export function periodAt(date = new Date()): Period {
  const h = date.getHours();
  if (h >= 6 && h < 11) return 'morning';
  if (h >= 11 && h < 17) return 'noon';
  if (h >= 17 && h < 21) return 'evening';
  return 'night';
}

function isCjkFont(value: unknown): value is CjkFontId {
  return typeof value === 'string' && (CJK_FONT_IDS as readonly string[]).includes(value);
}

function isLatinFont(value: unknown): value is LatinFontId {
  return typeof value === 'string' && (LATIN_FONT_IDS as readonly string[]).includes(value);
}

export function parsePrefs(raw: unknown): AppearancePrefs {
  if (!raw || typeof raw !== 'object') return DEFAULT_PREFS;
  const rec = raw as Record<string, unknown>;
  const mode = rec.mode === 'manual' ? 'manual' : 'schedule';
  const manual = readSurface(rec.manual ?? rec, DEFAULT_PREFS.manual);
  const schedule = { ...DEFAULT_PREFS.schedule };
  const src = rec.schedule;
  if (src && typeof src === 'object') {
    for (const period of PERIODS) {
      schedule[period] = readSurface(
        (src as Record<string, unknown>)[period],
        schedule[period],
      );
    }
  }
  return {
    mode,
    manual,
    schedule,
    cjkFont: isCjkFont(rec.cjkFont) ? rec.cjkFont : DEFAULT_PREFS.cjkFont,
    latinFont: isLatinFont(rec.latinFont) ? rec.latinFont : DEFAULT_PREFS.latinFont,
    workspace: parseWorkspace(rec.workspace),
  };
}

export function loadPrefs(): AppearancePrefs {
  try {
    const raw = localStorage.getItem(APPEARANCE_KEY);
    if (!raw) return DEFAULT_PREFS;
    return parsePrefs(JSON.parse(raw));
  } catch {
    return DEFAULT_PREFS;
  }
}

export function savePrefs(prefs: AppearancePrefs) {
  try {
    localStorage.setItem(APPEARANCE_KEY, JSON.stringify(prefs));
  } catch {
    /* private mode */
  }
  window.dispatchEvent(new Event(APPEARANCE_EVENT));
}

export function effectFor(
  prefs: AppearancePrefs,
  surface: Surface,
  period: Period,
): EffectId {
  if (prefs.mode === 'manual') return prefs.manual[surface];
  return prefs.schedule[period]?.[surface] ?? CALM[surface];
}

export function msUntilNextPeriod(date = new Date()): number {
  const h = date.getHours();
  const bounds = [6, 11, 17, 21, 30];
  const nextHour = bounds.find((b) => b > h) ?? 30;
  const next = new Date(date);
  if (nextHour === 30) {
    next.setDate(next.getDate() + 1);
    next.setHours(6, 0, 0, 0);
  } else {
    next.setHours(nextHour, 0, 0, 0);
  }
  return Math.max(1000, next.getTime() - date.getTime());
}
