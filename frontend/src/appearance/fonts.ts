export const CJK_FONT_IDS = [
  'system',
  'yahei',
  'hei',
  'song',
  'fangsong',
  'kai',
  'yuan',
] as const;

export type CjkFontId = (typeof CJK_FONT_IDS)[number];

export const LATIN_FONT_IDS = [
  'jakarta',
  'system',
  'inter',
  'ibm',
  'georgia',
  'sourceSerif',
  'times',
  'nunito',
  'mono',
] as const;

export type LatinFontId = (typeof LATIN_FONT_IDS)[number];

export interface FontOption<Id extends string> {
  id: Id;
  stack: string;
  group: 'sans' | 'serif' | 'script' | 'round' | 'mono';
  google?: string;
}

export const CJK_FONTS: readonly FontOption<CjkFontId>[] = [
  {
    id: 'system',
    group: 'sans',
    stack: '"PingFang SC", "Microsoft YaHei", "Noto Sans SC"',
  },
  {
    id: 'yahei',
    group: 'sans',
    stack: '"Microsoft YaHei", "PingFang SC", "Noto Sans SC"',
  },
  {
    id: 'hei',
    group: 'sans',
    stack: 'SimHei, STHeiti, "Heiti SC", "Microsoft YaHei"',
  },
  {
    id: 'song',
    group: 'serif',
    stack: 'SimSun, "Songti SC", STSong, "Noto Serif SC"',
  },
  {
    id: 'fangsong',
    group: 'serif',
    stack: 'FangSong, STFangsong, "Songti SC", SimSun',
  },
  {
    id: 'kai',
    group: 'script',
    stack: 'KaiTi, "Kaiti SC", STKaiti, "BiauKai"',
  },
  {
    id: 'yuan',
    group: 'round',
    stack: 'YouYuan, "Yuanti SC", "PingFang SC", "Microsoft YaHei"',
  },
];

export const LATIN_FONTS: readonly FontOption<LatinFontId>[] = [
  {
    id: 'jakarta',
    group: 'sans',
    stack: '"Plus Jakarta Sans"',
  },
  {
    id: 'system',
    group: 'sans',
    stack: 'system-ui, "Segoe UI", Roboto, "Helvetica Neue"',
  },
  {
    id: 'inter',
    group: 'sans',
    stack: 'Inter, system-ui, "Segoe UI"',
    google: 'Inter:ital,wght@0,400;0,500;0,600;0,700;1,400',
  },
  {
    id: 'ibm',
    group: 'sans',
    stack: '"IBM Plex Sans", "Segoe UI", system-ui',
    google: 'IBM+Plex+Sans:wght@400;500;600;700',
  },
  {
    id: 'georgia',
    group: 'serif',
    stack: 'Georgia, "Palatino Linotype", Palatino',
  },
  {
    id: 'sourceSerif',
    group: 'serif',
    stack: '"Source Serif 4", Georgia, "Times New Roman"',
    google: 'Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700',
  },
  {
    id: 'times',
    group: 'serif',
    stack: '"Times New Roman", Times, Georgia',
  },
  {
    id: 'nunito',
    group: 'round',
    stack: 'Nunito, "Segoe UI", system-ui',
    google: 'Nunito:wght@400;500;600;700',
  },
  {
    id: 'mono',
    group: 'mono',
    stack: '"JetBrains Mono", Consolas, "Courier New"',
  },
];

export const FONT_GROUP_ORDER = ['sans', 'serif', 'script', 'round', 'mono'] as const;

export const FONT_GROUP_KEY: Record<
  (typeof FONT_GROUP_ORDER)[number],
  `appearance.fontGroup${'Sans' | 'Serif' | 'Script' | 'Round' | 'Mono'}`
> = {
  sans: 'appearance.fontGroupSans',
  serif: 'appearance.fontGroupSerif',
  script: 'appearance.fontGroupScript',
  round: 'appearance.fontGroupRound',
  mono: 'appearance.fontGroupMono',
};

export const CJK_FONT_KEY: Record<CjkFontId, `appearance.font.cjk.${CjkFontId}`> = {
  system: 'appearance.font.cjk.system',
  yahei: 'appearance.font.cjk.yahei',
  hei: 'appearance.font.cjk.hei',
  song: 'appearance.font.cjk.song',
  fangsong: 'appearance.font.cjk.fangsong',
  kai: 'appearance.font.cjk.kai',
  yuan: 'appearance.font.cjk.yuan',
};

export const LATIN_FONT_KEY: Record<
  LatinFontId,
  `appearance.font.latin.${LatinFontId}`
> = {
  jakarta: 'appearance.font.latin.jakarta',
  system: 'appearance.font.latin.system',
  inter: 'appearance.font.latin.inter',
  ibm: 'appearance.font.latin.ibm',
  georgia: 'appearance.font.latin.georgia',
  sourceSerif: 'appearance.font.latin.sourceSerif',
  times: 'appearance.font.latin.times',
  nunito: 'appearance.font.latin.nunito',
  mono: 'appearance.font.latin.mono',
};

const WEBFONT_LINK_ID = 'nous-latin-webfont';

export function fontById<Id extends string>(
  list: readonly FontOption<Id>[],
  id: string | undefined,
  fallback: Id,
): FontOption<Id> {
  return list.find((item) => item.id === id) ?? list.find((item) => item.id === fallback)!;
}

export function applyUiFonts(latinId: LatinFontId, cjkId: CjkFontId) {
  if (typeof document === 'undefined') return;
  const latin = fontById(LATIN_FONTS, latinId, 'jakarta');
  const cjk = fontById(CJK_FONTS, cjkId, 'system');
  const root = document.documentElement;
  root.style.setProperty('--font-latin', latin.stack);
  root.style.setProperty('--font-cjk', cjk.stack);
  ensureLatinWebfont(latin.google);
}

function ensureLatinWebfont(google: string | undefined) {
  const href = google
    ? `https://fonts.googleapis.com/css2?family=${google}&display=swap`
    : null;
  let link = document.getElementById(WEBFONT_LINK_ID) as HTMLLinkElement | null;
  if (!href) {
    link?.remove();
    return;
  }
  if (!link) {
    link = document.createElement('link');
    link.id = WEBFONT_LINK_ID;
    link.rel = 'stylesheet';
    document.head.appendChild(link);
  }
  if (link.getAttribute('href') !== href) {
    link.setAttribute('href', href);
  }
}
