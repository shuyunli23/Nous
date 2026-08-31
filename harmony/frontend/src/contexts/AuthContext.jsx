import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../api/client';

const AuthContext = createContext(null);
const FROM_NOUS_KEY = 'harmony_from_nous';

let bootPromise = null;

function applySession(token, user, fromNous) {
  localStorage.setItem('token', token);
  localStorage.setItem('user', JSON.stringify(user));
  if (fromNous) {
    localStorage.setItem(FROM_NOUS_KEY, '1');
  } else {
    localStorage.removeItem(FROM_NOUS_KEY);
  }
}

function clearSession() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  localStorage.removeItem(FROM_NOUS_KEY);
}

function stripSsoParam() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has('sso')) return;
  url.searchParams.delete('sso');
  const search = url.searchParams.toString();
  window.history.replaceState({}, '', `${url.pathname}${search ? `?${search}` : ''}${url.hash}`);
}

function takeTicket() {
  const fromQuery = new URLSearchParams(window.location.search).get('sso');
  const fromStore = sessionStorage.getItem('harmony_sso_ticket');
  const ticket = (fromQuery || fromStore || '').trim();
  stripSsoParam();
  if (fromStore) sessionStorage.removeItem('harmony_sso_ticket');
  return ticket;
}

async function redeemTicket(ticket) {
  const res = await api.post('/auth/sso', { ticket });
  applySession(res.data.access_token, res.data.user, true);
  return res.data.user;
}

async function tryHostSso() {
  const accessRes = await fetch('/api/v1/harmony/access', {
    signal: AbortSignal.timeout(8000),
  });
  if (!accessRes.ok) return null;
  const access = await accessRes.json();
  if (!access.owner) return null;
  const ssoRes = await fetch('/api/v1/harmony/sso', {
    method: 'POST',
    signal: AbortSignal.timeout(8000),
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': 'local-dev',
    },
  });
  if (!ssoRes.ok) return null;
  const body = await ssoRes.json();
  return redeemTicket(body.ticket);
}

function bootSession() {
  if (!bootPromise) {
    bootPromise = (async () => {
      const ticket = takeTicket();
      if (ticket) {
        try {
          return await redeemTicket(ticket);
        } catch {
          /* Host auto-SSO below covers the owner. */
        }
      }
      try {
        const hostUser = await tryHostSso();
        if (hostUser) return hostUser;
      } catch {
        /* Not the Nous host — fall through to a saved Harmony account. */
      }
      const token = localStorage.getItem('token');
      const savedUser = localStorage.getItem('user');
      if (!token || !savedUser) return null;
      try {
        const res = await api.get('/auth/me');
        localStorage.setItem('user', JSON.stringify(res.data));
        return res.data;
      } catch {
        clearSession();
        return null;
      }
    })();
  }
  return bootPromise;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    bootSession()
      .then((nextUser) => {
        if (!cancelled) setUser(nextUser);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = async (username, password) => {
    const res = await api.post('/auth/login', { username, password });
    applySession(res.data.access_token, res.data.user, false);
    setUser(res.data.user);
  };

  const logout = () => {
    bootPromise = null;
    clearSession();
    setUser(null);
  };

  const updateUser = (updatedUser) => {
    setUser(updatedUser);
    localStorage.setItem('user', JSON.stringify(updatedUser));
  };

  const fromNous =
    typeof window !== 'undefined' && localStorage.getItem(FROM_NOUS_KEY) === '1';

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, updateUser, fromNous }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
