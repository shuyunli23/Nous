import { Component, useEffect, useState, type ReactNode } from 'react';

import { api } from '../api/client';
import { useI18n } from '../i18n';
import FloatingHarmonyPlayer from './FloatingHarmonyPlayer';
import UnlockScreen from './UnlockScreen';

type Access = { owner: boolean };
type Gate = 'checking' | 'owner' | 'locked';

class PlayerGuard extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return null;
    return this.props.children;
  }
}

function browserLooksLocal(): boolean {
  const host = window.location.hostname;
  return host === 'localhost' || host === '127.0.0.1' || host === '[::1]' || host === '::1';
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error('timeout')), ms);
    promise.then(
      (value) => {
        window.clearTimeout(timer);
        resolve(value);
      },
      (error: unknown) => {
        window.clearTimeout(timer);
        reject(error);
      },
    );
  });
}

/**
 * This machine (loopback) enters Nous without a password.
 * Another computer on the LAN must unlock with the admin password.
 * Harmony guest accounts still cannot enter Nous — send them to /harmony/.
 */
export default function OwnerGate({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [gate, setGate] = useState<Gate>('checking');
  const [hint, setHint] = useState('');

  useEffect(() => {
    let cancelled = false;
    withTimeout(api.get<Access>('/harmony/access'), 8000)
      .then((data) => {
        if (!cancelled) setGate(data.owner ? 'owner' : 'locked');
      })
      .catch(() => {
        if (cancelled) return;
        if (browserLooksLocal()) {
          setGate('owner');
          return;
        }
        setHint(t('unlock.offline'));
        setGate('locked');
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  if (gate === 'checking') {
    return (
      <div className="unlock-gate">
        <p className="unlock-gate__checking">{t('unlock.checking')}</p>
      </div>
    );
  }

  if (gate === 'locked') {
    return <UnlockScreen backendHint={hint} onUnlocked={() => setGate('owner')} />;
  }

  return (
    <>
      {children}
      <PlayerGuard>
        <FloatingHarmonyPlayer />
      </PlayerGuard>
    </>
  );
}
