/**
 * V4 useTheme — light/dark toggle.
 *
 * Ported from v3/theme/useTheme.ts with the root class changed to
 * `.v4-root`. Same contract:
 *   - Default: system preference (prefers-color-scheme)
 *   - User choice persists to localStorage key `v4.theme`
 *   - Applies `data-theme` attribute on every `.v4-root` element
 *   - Respects `prefers-reduced-motion` (set in the CSS not here)
 *
 * Why a local copy vs importing from v3: v3 and v4 are sibling subtrees
 * and must not cross-import per the repo's reorg rules. Shared concerns
 * go under shared/, but a 100-line theme hook per variant is cheaper
 * than inventing a shared-theme abstraction.
 */

import { useCallback, useEffect, useState } from 'react';

export type Theme = 'dark' | 'light';

const STORAGE_KEY = 'v4.theme';
const ROOT_CLASS = 'v4-root';

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
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function initialTheme(): Theme {
  return readStored() ?? readSystemPreference();
}

function applyToDom(theme: Theme): void {
  if (typeof document === 'undefined') return;
  document.querySelectorAll(`.${ROOT_CLASS}`).forEach((el) => {
    (el as HTMLElement).dataset.theme = theme;
  });
}

export function useTheme(): {
  theme: Theme;
  setTheme: (next: Theme) => void;
  toggle: () => void;
} {
  const [theme, setThemeState] = useState<Theme>(() => initialTheme());

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

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    if (readStored()) return;
    const mql = window.matchMedia('(prefers-color-scheme: light)');
    const onChange = (evt: MediaQueryListEvent) => {
      setThemeState(evt.matches ? 'light' : 'dark');
    };
    if (mql.addEventListener) {
      mql.addEventListener('change', onChange);
      return () => mql.removeEventListener('change', onChange);
    }
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
