import { Link } from 'react-router-dom';

import { useI18n } from '../i18n';
import AppShell from './AppShell';

function isKnowledgeHome(pathname: string): boolean {
  if (
    pathname.startsWith('/knowledge/search') ||
    pathname.startsWith('/knowledge/graph') ||
    pathname.startsWith('/knowledge/assistant')
  ) {
    return false;
  }
  return pathname === '/knowledge' || pathname.startsWith('/knowledge/');
}

export default function KnowledgeLayout() {
  const { t } = useI18n();

  return (
    <AppShell
      brandName="NexusMind"
      brandTag={t('layout.nexusTag')}
      brandVariant="nexus"
      navAria={t('nav.knowledgeAria')}
      beforeNav={
        <Link to="/" className="nav-back">
          <img className="nav-back__mark" src="/nous-mark.png" alt="" aria-hidden="true" />
          <span className="nav-link__copy">
            <span className="nav-back__label">{t('nav.backNous')}</span>
            <span className="nav-back__hint">{t('nav.backNousHint')}</span>
          </span>
        </Link>
      }
      nav={[
        {
          to: '/knowledge',
          label: t('nav.knowledge'),
          hint: t('nav.knowledgeHint'),
          icon: 'notes',
          isActive: isKnowledgeHome,
        },
        {
          to: '/knowledge/search',
          label: t('nav.search'),
          hint: t('nav.searchHint'),
          icon: 'search',
        },
        {
          to: '/knowledge/assistant',
          label: t('nav.assistant'),
          hint: t('nav.assistantHint'),
          icon: 'assistant',
        },
        {
          to: '/knowledge/graph',
          label: t('nav.graph'),
          hint: t('nav.graphHint'),
          icon: 'graph',
        },
      ]}
    />
  );
}
