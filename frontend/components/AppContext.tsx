"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { DEFAULT_USER, loadUser, saveUser } from "@/lib/api";
import type { AgentStatus, CurrentUser, RunRecord } from "@/lib/types";
import { usePoll } from "@/lib/usePoll";

export type ThemeChoice = "system" | "light" | "dark";
const THEME_KEY = "p113.theme";
export const RUNS_LIMIT = 100; // API trả tối đa 100 lần chạy mới nhất

interface AppState {
  status: AgentStatus | null;
  statusError: string;
  user: CurrentUser;
  setUser: (user: CurrentUser) => void;
  theme: ThemeChoice;
  setTheme: (theme: ThemeChoice) => void;
  dark: boolean;
  /** Danh sách lần chạy dùng chung (chuông, trang chủ, tìm kiếm, bảng) — một lần hỏi API cho cả app. */
  runs: RunRecord[] | null;
  runsError: string;
  refreshRuns: () => Promise<void>;
}

const AppContext = createContext<AppState | null>(null);

function readTheme(): ThemeChoice {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

function useSystemDark(): boolean {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setDark(query.matches);
    const first = setTimeout(update, 0);
    query.addEventListener("change", update);
    return () => {
      clearTimeout(first);
      query.removeEventListener("change", update);
    };
  }, []);
  return dark;
}

function useStoredSettings(): [CurrentUser, (u: CurrentUser) => void, ThemeChoice, (t: ThemeChoice) => void] {
  const [user, setUserState] = useState<CurrentUser>(DEFAULT_USER);
  const [theme, setThemeState] = useState<ThemeChoice>("system");
  useEffect(() => {
    const first = setTimeout(() => {
      setUserState(loadUser());
      setThemeState(readTheme());
    }, 0);
    return () => clearTimeout(first);
  }, []);
  const setUser = useCallback((next: CurrentUser) => {
    saveUser(next);
    setUserState(next);
  }, []);
  const setTheme = useCallback((next: ThemeChoice) => {
    try {
      if (next === "system") localStorage.removeItem(THEME_KEY);
      else localStorage.setItem(THEME_KEY, next);
    } catch {
      // không lưu được: chỉ áp dụng trong phiên này
    }
    if (next === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = next;
    setThemeState(next);
  }, []);
  return [user, setUser, theme, setTheme];
}

export function AppProvider({ children }: { children: ReactNode }) {
  const polled = usePoll<AgentStatus>("/status", 30000);
  const runs = usePoll<RunRecord[]>(`/runs?limit=${RUNS_LIMIT}`, 6000);
  const [user, setUser, theme, setTheme] = useStoredSettings();
  const systemDark = useSystemDark();
  const dark = theme === "dark" || (theme === "system" && systemDark);
  const value = useMemo<AppState>(
    () => ({
      status: polled.data,
      statusError: polled.error,
      user,
      setUser,
      theme,
      setTheme,
      dark,
      runs: runs.data,
      runsError: runs.error,
      refreshRuns: runs.refresh,
    }),
    [polled.data, polled.error, user, setUser, theme, setTheme, dark, runs.data, runs.error, runs.refresh],
  );
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppState {
  const state = useContext(AppContext);
  if (!state) throw new Error("useApp phải nằm trong AppProvider");
  return state;
}
