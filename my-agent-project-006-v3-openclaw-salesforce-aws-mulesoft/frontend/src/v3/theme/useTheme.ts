/**
 * useTheme — v3 light/dark mode (roadmap item #5).
 *
 * Contract:
 *   - Returns the current theme ('dark' | 'light') and a setter.
 *   - Persists choice to localStorage (`v3.theme`).
 *   - Falls back to `prefers-color-scheme` when no choice stored.
 *   - Applies `data-theme` attribute to the `.v3-root` element on change.
 *
 * Why a tiny hook instead of Zustand: theme is a v3-only concern, no
 * cross-component state flow, and adding it to the shared session store
 * would leak v3 details into v1/v2.
 *
 * Why `data-theme` on `.v3-root` not `<html>`:
 *   - Scope: v3 theming must not affect v1 or v2 styling.
 *   - All v3 CSS already scopes under `.v3-root`, so mirroring the theme
 *     attribute there is the cleanest override anchor.
 */

import { useCallback, useEffect, useState } from 'react';

export type Theme = 'dark' | 'light';

const STORAGE_KEY = 'v3.theme';
const ROOT_CLASS = 'v3-root';

function readStored(): Theme | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === 'dark' || raw === 'light') return raw;
    return null;
  } catch {
    return null;
  }
}

function readSystemPreference(): Theme {
  if (typeof window === 'undefined' || !window.matchMedia) return 'dark';
  return window.matchMedia('(prefers-color-scheme: light)').matches
    ? 'light'
    : 'dark';
}

/**
 * Compute the initial theme without touching the DOM. Safe for SSR /
 * initial render. The effect below applies it to the DOM.
 */
export function initialTheme(): Theme {
  return readStored() ?? readSystemPreference();
}

function applyToDom(theme: Theme): void {
  if (typeof document === 'undefined') return;
  // Prefer the nearest .v3-root; fall back to the first one on page.
  const roots = document.querySelectorAll(`.${ROOT_CLASS}`);
  roots.forEach((el) => {
    (el as HTMLElement).dataset.theme = theme;
  });
}

export function useTheme(): {
  theme: Theme;
  setTheme: (next: Theme) => void;
  toggle: () => void;
} {
  const [theme, setThemeState] = useState<Theme>(() => initialTheme());

  // Apply whenever the state changes OR on mount (ensures root has the
  // attribute even before the first toggle).
  useEffect(() => {
    applyToDom(theme);
    if (typeof window !== 'undefined') {
      try {
        window.localStorage.setItem(STORAGE_KEY, theme);
      } catch {
        /* quota / private mode — ignore */
      }
    }
  }, [theme]);

  // Respect system changes ONLY when the user hasn't explicitly chosen.
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    if (readStored()) return; // user made a choice — don't override
    const mql = window.matchMedia('(prefers-color-scheme: light)');
    const onChange = (evt: MediaQueryListEvent) => {
      setThemeState(evt.matches ? 'light' : 'dark');
    };
    // addEventListener is the modern API; addListener is the legacy fallback
    if (mql.addEventListener) {
      mql.addEventListener('change', onChange);
      return () => mql.removeEventListener('change', onChange);
    }
    // Legacy Safari (≤ 13) doesn't have addEventListener on MediaQueryList
    (mql as unknown as { addListener: (cb: (e: MediaQueryListEvent) => void) => void }).addListener(onChange);
    return () => {
      (mql as unknown as { removeListener: (cb: (e: MediaQueryListEvent) => void) => void }).removeListener(onChange);
    };
  }, []);

  const setTheme = useCallback((next: Theme) => setThemeState(next), []);
  const toggle = useCallback(
    () => setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark')),
    [],
  );

  return { theme, setTheme, toggle };
}
