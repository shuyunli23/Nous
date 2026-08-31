import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import {
  applyDocumentLocale,
  catalogs,
  detectLocale,
  setCurrentLocale,
  STORAGE_KEY,
  translate,
  type Locale,
  type MessageKey,
  type Messages,
  type Vars,
} from './core';

interface I18nContextValue {
  locale: Locale;
  messages: Messages;
  setLocale: (next: Locale) => void;
  t: (path: MessageKey, vars?: Vars) => string;
  dateLocale: string;
  formatDateTime: (iso: string) => string;
  formatDate: (iso: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    const initial = detectLocale();
    setCurrentLocale(initial);
    return initial;
  });

  const setLocale = useCallback((next: Locale) => {
    setCurrentLocale(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
    applyDocumentLocale(next);
    setLocaleState(next);
  }, []);

  useEffect(() => {
    setCurrentLocale(locale);
    applyDocumentLocale(locale);
  }, [locale]);

  const value = useMemo<I18nContextValue>(() => {
    const dateLocale = locale === 'zh' ? 'zh-CN' : 'en-US';
    return {
      locale,
      messages: catalogs[locale],
      setLocale,
      t: (path, vars) => translate(path, vars, locale),
      dateLocale,
      formatDateTime: (iso) => {
        try {
          return new Date(iso).toLocaleString(dateLocale);
        } catch {
          return iso;
        }
      },
      formatDate: (iso) => {
        try {
          return new Date(iso).toLocaleDateString(dateLocale);
        } catch {
          return iso;
        }
      },
    };
  }, [locale, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error('useI18n must be used within LanguageProvider');
  }
  return ctx;
}
