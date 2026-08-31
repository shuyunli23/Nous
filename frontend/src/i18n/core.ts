import { en } from './en';
import { zh, type Messages } from './zh';

export type Locale = 'zh' | 'en';
export type { Messages };
export type Vars = Record<string, string | number | null | undefined>;

export const STORAGE_KEY = 'nous.locale';

export const catalogs: Record<Locale, Messages> = { zh, en };

type LeafPath<T, Prefix extends string = ''> = {
  [K in keyof T & string]: T[K] extends string
    ? `${Prefix}${K}`
    : T[K] extends readonly string[]
      ? never
      : T[K] extends object
        ? LeafPath<T[K], `${Prefix}${K}.`>
        : never;
}[keyof T & string];

export type MessageKey = LeafPath<Messages>;

function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, key: string) =>
    vars[key] == null ? '' : String(vars[key]),
  );
}

function lookup(messages: Messages, path: string): unknown {
  let current: unknown = messages;
  for (const part of path.split('.')) {
    if (!current || typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

export function detectLocale(): Locale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'zh' || saved === 'en') return saved;
  } catch {
    /* private mode */
  }
  const nav =
    typeof navigator !== 'undefined' ? navigator.language.toLowerCase() : 'zh';
  return nav.startsWith('zh') ? 'zh' : 'en';
}

export function applyDocumentLocale(locale: Locale) {
  const meta = catalogs[locale].meta;
  document.documentElement.lang = meta.htmlLang;
  document.title = meta.title;
}

let currentLocale: Locale =
  typeof window !== 'undefined' ? detectLocale() : 'zh';

export function getLocale(): Locale {
  return currentLocale;
}

export function setCurrentLocale(next: Locale) {
  currentLocale = next;
}

export function translate(
  path: MessageKey,
  vars?: Vars,
  locale?: Locale,
): string {
  const messages = catalogs[locale ?? currentLocale];
  const value = lookup(messages, path);
  if (typeof value !== 'string') return path;
  return interpolate(value, vars);
}

/** For non-React modules such as the API client. */
export const t = translate;
