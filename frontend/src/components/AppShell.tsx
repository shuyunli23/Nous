import { Component, useEffect, useId, useState, type ReactNode } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

import { getHealth } from '../api/chat';
import type { HealthResponse } from '../api/types';
import AmbientLayer from '../appearance/AmbientLayer';
import { useAmbientEffect } from '../appearance/AppearanceProvider';
import WorkspaceBg from '../appearance/WorkspaceBg';
import { useI18n, type Locale } from '../i18n';
import NavIcon, { type NavIconName } from './NavIcon';

export interface ShellNavItem {
  to: string;
  label: string;
  hint: string;
  icon?: NavIconName;
  end?: boolean;
  isActive?: (pathname: string) => boolean;
}

interface AppShellProps {
  brandName: string;
  brandTag: string;
  brandVariant?: 'nous' | 'nexus';
  navAria: string;
  nav: ShellNavItem[];
  beforeNav?: ReactNode;
  afterNav?: ReactNode;
}

function BrandMark({ variant }: { variant: 'nous' | 'nexus' }) {
  if (variant === 'nexus') {
    return (
      <img
        className="brand-mark brand-mark--nexus"
        src="/nexus-mark.svg"
        alt=""
        draggable={false}
      />
    );
  }

  return (
    <img
      className="brand-mark"
      src="/nous-mark.png"
      alt=""
      draggable={false}
    />
  );
}

export default function AppShell({
  brandName,
  brandTag,
  brandVariant = 'nous',
  navAria,
  nav,
  beforeNav,
  afterNav,
}: AppShellProps) {
  const { t, locale, setLocale } = useI18n();
  const sidebarFx = useAmbientEffect('sidebar');
  const { pathname } = useLocation();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const sidebarId = useId();

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!navOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setNavOpen(false);
    };
    window.addEventListener('keydown', onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = previous;
    };
  }, [navOpen]);

  function langButton(code: Locale, label: string) {
    return (
      <button
        type="button"
        className={
          locale === code
            ? 'lang-switch__btn lang-switch__btn--active'
            : 'lang-switch__btn'
        }
        aria-pressed={locale === code}
        onClick={() => setLocale(code)}
      >
        {label}
      </button>
    );
  }

  const brand = (
    <>
      <BrandMark variant={brandVariant} />
      <div className="brand-copy">
        <span className="brand-name">{brandName}</span>
        <span className="brand-tag">{brandTag}</span>
      </div>
    </>
  );

  return (
    <div
      className={
        [
          'app',
          navOpen ? 'app--nav-open' : '',
          brandVariant === 'nexus' ? 'app--nexus' : '',
        ]
          .filter(Boolean)
          .join(' ')
      }
    >
      <header className="app-topbar">
        <button
          type="button"
          className="menu-btn"
          aria-label={navOpen ? t('layout.closeMenu') : t('layout.menu')}
          aria-expanded={navOpen}
          aria-controls={sidebarId}
          onClick={() => setNavOpen((open) => !open)}
        >
          <span className="menu-btn__bar" />
          <span className="menu-btn__bar" />
          <span className="menu-btn__bar" />
        </button>
        <div className="app-topbar__brand">{brand}</div>
      </header>

      {navOpen ? (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label={t('layout.closeMenu')}
          onClick={() => setNavOpen(false)}
        />
      ) : null}

      <aside
        className={sidebarFx !== 'none' ? 'sidebar sidebar--ambient' : 'sidebar'}
        id={sidebarId}
      >
        <AmbientLayer surface="sidebar" />
        <div className="sidebar__brand">{brand}</div>

        {beforeNav}

        <nav className="sidebar__nav" aria-label={navAria}>
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => {
                const active = item.isActive
                  ? item.isActive(pathname)
                  : isActive;
                return active ? 'nav-link nav-link--active' : 'nav-link';
              }}
            >
              {item.icon ? (
                <span className="nav-link__icon">
                  <NavIcon name={item.icon} />
                </span>
              ) : null}
              <span className="nav-link__copy">
                <span className="nav-link__label">{item.label}</span>
                <span className="nav-link__hint">{item.hint}</span>
              </span>
            </NavLink>
          ))}
        </nav>

        {afterNav}

        <div className="lang-switch" role="group" aria-label={t('layout.langSwitchAria')}>
          {langButton('zh', t('layout.langZh'))}
          {langButton('en', t('layout.langEn'))}
        </div>

        <div className="sidebar__footer">
          {health ? (
            <>
              <span className="status-dot" data-ok={health.status === 'ok'} />
              <span>
                {health.status === 'ok'
                  ? t('layout.online')
                  : t('layout.degraded')}{' '}
                · {health.environment}
              </span>
              <span title={`${health.llm_provider} · ${health.llm_model}`}>
                {health.llm_configured
                  ? health.llm_model
                  : t('layout.modelUnconfigured')}
              </span>
            </>
          ) : (
            <span>{t('layout.backendOffline')}</span>
          )}
        </div>
      </aside>

      <main className="main">
        <WorkspaceBg />
        <div className="main__content">
          <RouteErrorBoundary key={pathname} fallback={t('common.renderFailed')}>
            <Outlet />
          </RouteErrorBoundary>
        </div>
      </main>
    </div>
  );
}

class RouteErrorBoundary extends Component<
  { children: ReactNode; fallback: string },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="page">
          <p className="banner banner--error">{this.props.fallback}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
