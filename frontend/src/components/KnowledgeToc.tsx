import { useEffect, useState, type MouseEvent } from 'react';

import type { TocEntry } from '../lib/markdownToc';
import { useI18n } from '../i18n';

interface KnowledgeTocProps {
  entries: TocEntry[];
  article: HTMLElement | null;
}

export default function KnowledgeToc({ entries, article }: KnowledgeTocProps) {
  const { t } = useI18n();
  const [activeId, setActiveId] = useState(entries[0]?.id ?? '');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!article || entries.length === 0) return;

    const headings = entries
      .map((entry) => headingById(article, entry.id))
      .filter((el): el is HTMLElement => el instanceof HTMLElement);
    if (headings.length === 0) return;

    const observer = new IntersectionObserver(
      (records) => {
        const visible = records
          .filter((record) => record.isIntersecting)
          .sort(
            (a, b) =>
              a.boundingClientRect.top - b.boundingClientRect.top,
          );
        const first = visible[0]?.target;
        if (first instanceof HTMLElement && first.id) {
          setActiveId(first.id);
        }
      },
      { rootMargin: '-12% 0px -70% 0px', threshold: [0, 1] },
    );
    headings.forEach((heading) => observer.observe(heading));

    const hash = readHash();
    if (hash) {
      const target = headingById(article, hash);
      if (target) {
        setActiveId(hash);
        window.requestAnimationFrame(() => {
          target.scrollIntoView({ block: 'start' });
        });
      }
    }
    return () => observer.disconnect();
  }, [article, entries]);

  if (entries.length === 0) return null;

  function jump(event: MouseEvent<HTMLAnchorElement>, id: string) {
    event.preventDefault();
    const target = headingById(article, id);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveId(id);
      setOpen(false);
      window.history.replaceState(null, '', `#${encodeURIComponent(id)}`);
    }
  }

  const list = (
    <nav className="km-toc__nav" aria-label={t('km.toc')}>
      {entries.map((entry) => (
        <a
          key={entry.id}
          href={`#${encodeURIComponent(entry.id)}`}
          className={
            entry.id === activeId
              ? `km-toc__item km-toc__item--l${entry.level} km-toc__item--active`
              : `km-toc__item km-toc__item--l${entry.level}`
          }
          onClick={(event) => jump(event, entry.id)}
        >
          {entry.text}
        </a>
      ))}
    </nav>
  );

  return (
    <>
      <button
        type="button"
        className="km-toc-toggle"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {t('km.toc')}
      </button>
      {open ? (
        <button
          type="button"
          className="km-toc-backdrop"
          aria-label={t('common.close')}
          onClick={() => setOpen(false)}
        />
      ) : null}
      <aside className={open ? 'km-toc km-toc--open' : 'km-toc'}>
        <div className="km-toc__head">
          <p className="km-section-title">{t('km.toc')}</p>
          <button
            type="button"
            className="km-toc__close"
            onClick={() => setOpen(false)}
          >
            {t('common.close')}
          </button>
        </div>
        {list}
      </aside>
    </>
  );
}

function headingById(root: HTMLElement | null, id: string): HTMLElement | null {
  if (!root || !id) return null;
  if (root.id === id) return root;
  const matches = root.querySelectorAll('[id]');
  for (const node of matches) {
    if (node instanceof HTMLElement && node.id === id) return node;
  }
  return null;
}

function readHash(): string {
  const raw = window.location.hash.replace(/^#/, '');
  if (!raw) return '';
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}
