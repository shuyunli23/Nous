import type { CjkFontId, LatinFontId } from './fonts';
import type { WorkspacePrefs } from './workspace';

export const EFFECT_IDS = [
  'none',
  'orbs',
  'aurora',
  'fireworks',
  'starfield',
  'particles',
  'waves',
  'neon',
  'sunset',
  'rainbow',
  'sakura',
  'lightning',
  'lava',
] as const;

export type EffectId = (typeof EFFECT_IDS)[number];

export const PERIODS = ['morning', 'noon', 'evening', 'night'] as const;
export type Period = (typeof PERIODS)[number];

export type Surface = 'graph' | 'sidebar';

export type SurfaceEffects = Record<Surface, EffectId>;

export interface AppearancePrefs {
  mode: 'manual' | 'schedule';
  manual: SurfaceEffects;
  schedule: Record<Period, SurfaceEffects>;
  cjkFont: CjkFontId;
  latinFont: LatinFontId;
  workspace: WorkspacePrefs;
}

export const EFFECT_NAME_KEY: Record<EffectId, `appearance.fx.${EffectId}`> = {
  none: 'appearance.fx.none',
  orbs: 'appearance.fx.orbs',
  aurora: 'appearance.fx.aurora',
  fireworks: 'appearance.fx.fireworks',
  starfield: 'appearance.fx.starfield',
  particles: 'appearance.fx.particles',
  waves: 'appearance.fx.waves',
  neon: 'appearance.fx.neon',
  sunset: 'appearance.fx.sunset',
  rainbow: 'appearance.fx.rainbow',
  sakura: 'appearance.fx.sakura',
  lightning: 'appearance.fx.lightning',
  lava: 'appearance.fx.lava',
};

export const PERIOD_KEY: Record<Period, `appearance.period.${Period}`> = {
  morning: 'appearance.period.morning',
  noon: 'appearance.period.noon',
  evening: 'appearance.period.evening',
  night: 'appearance.period.night',
};

export const PERIOD_HOURS_KEY: Record<Period, `appearance.hours.${Period}`> = {
  morning: 'appearance.hours.morning',
  noon: 'appearance.hours.noon',
  evening: 'appearance.hours.evening',
  night: 'appearance.hours.night',
};
