import type { ReactNode } from 'react';
import NexusMark from './NexusMark';

// Menu geometry: Lucide 1.17.0, matching the approved soft-duotone preview.
// Copyright Lucide contributors; ISC license (see lucide-LICENSE.txt).

export type NavIconName =
  | 'workbench'
  | 'history'
  | 'skills'
  | 'knowledge'
  | 'settings'
  | 'harmony'
  | 'search'
  | 'assistant'
  | 'graph'
  | 'notes';

function Icon({ children, duotone = false }: { children: ReactNode; duotone?: boolean }) {
  return (
    <svg
      className="nav-link__glyph"
      viewBox="0 0 24 24"
      fill={duotone ? "#6dd9cb22" : "none"}
      stroke="currentColor"
      strokeWidth={duotone ? 1.7 : 1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export default function NavIcon({ name }: { name: NavIconName }) {
  switch (name) {
    case 'workbench':
      return (
        <Icon duotone>
          <rect width="7" height="9" x="3" y="3" rx="1" />
          <rect width="7" height="5" x="14" y="3" rx="1" />
          <rect width="7" height="9" x="14" y="12" rx="1" />
          <rect width="7" height="5" x="3" y="16" rx="1" />
        </Icon>
      );
    case 'history':
      return (
        <Icon duotone>
          <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
          <path d="M3 3v5h5" />
          <path d="M12 7v5l4 2" />
        </Icon>
      );
    case 'skills':
      return (
        <Icon duotone>
          <path d="M10 22V7a1 1 0 0 0-1-1H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5a1 1 0 0 0-1-1H2" />
          <rect x="14" y="2" width="8" height="8" rx="1" />
        </Icon>
      );
    case 'knowledge':
      return <NexusMark className="nav-link__glyph nav-link__glyph--nexus" />;
    case 'settings':
      return (
        <Icon duotone>
          <path d="M14 17H5" />
          <path d="M19 7h-9" />
          <circle cx="17" cy="17" r="3" />
          <circle cx="7" cy="7" r="3" />
        </Icon>
      );
    case 'harmony':
      return (
        <Icon>
          <path d="M9 18V7l10-2v11" />
          <circle cx="7" cy="18" r="2.4" />
          <circle cx="17" cy="16" r="2.4" />
        </Icon>
      );
    case 'search':
      return (
        <Icon duotone>
          <path d="M3 7V5a2 2 0 0 1 2-2h2" />
          <path d="M17 3h2a2 2 0 0 1 2 2v2" />
          <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
          <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
          <circle cx="12" cy="12" r="3" />
          <path d="m16 16-1.9-1.9" />
        </Icon>
      );
    case 'assistant':
      return (
        <Icon duotone>
          <path d="M12 6V2H8" />
          <path d="M15 11v2" />
          <path d="M2 12h2" />
          <path d="M20 12h2" />
          <path d="M20 16a2 2 0 0 1-2 2H8.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 4 20.286V8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2z" />
          <path d="M9 11v2" />
        </Icon>
      );
    case 'graph':
      return (
        <Icon duotone>
          <path d="m10.586 5.414-5.172 5.172" />
          <path d="m18.586 13.414-5.172 5.172" />
          <path d="M6 12h12" />
          <circle cx="12" cy="20" r="2" />
          <circle cx="12" cy="4" r="2" />
          <circle cx="20" cy="12" r="2" />
          <circle cx="4" cy="12" r="2" />
        </Icon>
      );
    case 'notes':
      return (
        <Icon duotone>
          <path d="M2 6h4" />
          <path d="M2 10h4" />
          <path d="M2 14h4" />
          <path d="M2 18h4" />
          <rect width="16" height="20" x="4" y="2" rx="2" />
          <path d="M15 2v20" />
          <path d="M15 7h5" />
          <path d="M15 12h5" />
          <path d="M15 17h5" />
        </Icon>
      );
  }
}
