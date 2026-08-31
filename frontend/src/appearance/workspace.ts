export const WORKSPACE_SCENE_IDS = [
  'plain',
  'mesh',
  'grain',
  'dawn',
  'dusk',
  'aurora',
  'ocean',
  'forest',
  'alpine',
  'sunset',
] as const;

export type WorkspaceSceneId = (typeof WORKSPACE_SCENE_IDS)[number];

export const SOFT_SCENE_IDS = ['plain', 'mesh', 'grain', 'dawn', 'dusk'] as const;
export const PACK_SCENE_IDS = ['aurora', 'ocean', 'forest', 'alpine', 'sunset'] as const;

export type WorkspaceSource = 'scene' | 'custom';

export interface WorkspacePrefs {
  source: WorkspaceSource;
  scene: WorkspaceSceneId;
  customId: string | null;
  motion: boolean;
  veil: number;
}

export const DEFAULT_WORKSPACE: WorkspacePrefs = {
  source: 'scene',
  scene: 'plain',
  customId: null,
  motion: true,
  veil: 0.48,
};

export const VEIL_MIN = 0.22;
export const VEIL_MAX = 0.9;

export const SCENE_NAME_KEY: Record<
  WorkspaceSceneId,
  `appearance.ws.scene.${WorkspaceSceneId}`
> = {
  plain: 'appearance.ws.scene.plain',
  mesh: 'appearance.ws.scene.mesh',
  grain: 'appearance.ws.scene.grain',
  dawn: 'appearance.ws.scene.dawn',
  dusk: 'appearance.ws.scene.dusk',
  aurora: 'appearance.ws.scene.aurora',
  ocean: 'appearance.ws.scene.ocean',
  forest: 'appearance.ws.scene.forest',
  alpine: 'appearance.ws.scene.alpine',
  sunset: 'appearance.ws.scene.sunset',
};

export const SCENE_HINT_KEY: Record<
  WorkspaceSceneId,
  `appearance.ws.hint.${WorkspaceSceneId}`
> = {
  plain: 'appearance.ws.hint.plain',
  mesh: 'appearance.ws.hint.mesh',
  grain: 'appearance.ws.hint.grain',
  dawn: 'appearance.ws.hint.dawn',
  dusk: 'appearance.ws.hint.dusk',
  aurora: 'appearance.ws.hint.aurora',
  ocean: 'appearance.ws.hint.ocean',
  forest: 'appearance.ws.hint.forest',
  alpine: 'appearance.ws.hint.alpine',
  sunset: 'appearance.ws.hint.sunset',
};

export function isWorkspaceScene(value: unknown): value is WorkspaceSceneId {
  return (
    typeof value === 'string' &&
    (WORKSPACE_SCENE_IDS as readonly string[]).includes(value)
  );
}

export function clampVeil(value: unknown, fallback = DEFAULT_WORKSPACE.veil): number {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(VEIL_MAX, Math.max(VEIL_MIN, n));
}

export function parseWorkspace(raw: unknown): WorkspacePrefs {
  if (!raw || typeof raw !== 'object') return DEFAULT_WORKSPACE;
  const rec = raw as Record<string, unknown>;
  const source: WorkspaceSource = rec.source === 'custom' ? 'custom' : 'scene';
  return {
    source,
    scene: isWorkspaceScene(rec.scene) ? rec.scene : DEFAULT_WORKSPACE.scene,
    customId: typeof rec.customId === 'string' && rec.customId ? rec.customId : null,
    motion: rec.motion !== false,
    veil: clampVeil(rec.veil),
  };
}

export function packSrc(id: WorkspaceSceneId): string | null {
  if (!(PACK_SCENE_IDS as readonly string[]).includes(id)) return null;
  return `/bg/${id}.svg?v=2`;
}
