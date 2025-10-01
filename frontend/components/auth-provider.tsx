"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

type User = {
  email: string;
  name?: string;
};

type AuthContextValue = {
  user: User | null;
  initializing: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const STORAGE_KEY = "lona.auth";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as User;
        setUser(parsed);
      }
    } catch (error) {
      console.warn("Failed to parse auth session", error);
    } finally {
      setInitializing(false);
    }
  }, []);

  const persist = (next: User | null) => {
    if (typeof window === "undefined") return;
    if (next) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  };

  const login = async (email: string, password: string) => {
    await new Promise((resolve) => setTimeout(resolve, 350));
    const nextUser: User = {
      email,
      name: email.split("@")[0]?.replace(/[^a-zA-Z0-9]/g, " ") || "Trader"
    };
    setUser(nextUser);
    persist(nextUser);
  };

  const register = async (email: string, password: string) => {
    await login(email, password);
  };

  const logout = () => {
    setUser(null);
    persist(null);
  };

  const value = useMemo<AuthContextValue>(
    () => ({ user, initializing, login, register, logout }),
    [user, initializing]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
