import type { ReactNode } from 'react';

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

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      className="nav-link__glyph"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
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
        <Icon>
          <path d="M4 7.5A2.5 2.5 0 0 1 6.5 5h11A2.5 2.5 0 0 1 20 7.5v8a2.5 2.5 0 0 1-2.5 2.5H9l-4 3v-3.2A2.5 2.5 0 0 1 4 15.5z" />
        </Icon>
      );
    case 'history':
      return (
        <Icon>
          <circle cx="12" cy="12" r="7.5" />
          <path d="M12 8.2V12l2.5 1.5" />
          <path d="M4.6 7.2 4 4.8l2.5.4" />
        </Icon>
      );
    case 'skills':
      return (
        <Icon>
          <path d="M12 3.8 13.5 8h4.6l-3.7 2.8 1.4 4.4L12 12.6 8.2 15.2 9.6 10.8 5.9 8h4.6z" />
        </Icon>
      );
    case 'knowledge':
      return (
        <Icon>
          <path d="M5 6.4c1.7-1 3.8-1 5.5 0v11.4c-1.7-1-3.8-1-5.5 0z" />
          <path d="M19 6.4c-1.7-1-3.8-1-5.5 0v11.4c1.7-1 3.8-1 5.5 0z" />
        </Icon>
      );
    case 'settings':
      return (
        <Icon>
          <path d="M5 8.5h14" />
          <path d="M5 15.5h14" />
          <circle cx="10" cy="8.5" r="1.8" />
          <circle cx="14" cy="15.5" r="1.8" />
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
        <Icon>
          <circle cx="11" cy="11" r="6.5" />
          <path d="M16.2 16.2 20.5 20.5" />
        </Icon>
      );
    case 'assistant':
      return (
        <Icon>
          <path d="M12 4.5 13.2 8h3.8l-3 2.3 1.1 3.6L12 11.7 8.9 13.9 10 10.3l-3-2.3h3.8z" />
        </Icon>
      );
    case 'graph':
      return (
        <Icon>
          <circle cx="6.5" cy="17" r="2.2" />
          <circle cx="17.5" cy="6.5" r="2.2" />
          <circle cx="17.5" cy="17" r="2.2" />
          <path d="M8.3 15.6 15.6 8.2" />
          <path d="M8.7 17.2h6.4" />
        </Icon>
      );
    case 'notes':
      return (
        <Icon>
          <path d="M7.5 4.5h9A2 2 0 0 1 18.5 6.5v13l-3-1.5-3 1.5-3-1.5-3 1.5v-13A2 2 0 0 1 7.5 4.5z" />
          <path d="M9.5 9h5.5M9.5 12.5h5.5" />
        </Icon>
      );
  }
}
