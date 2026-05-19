import React, { createContext, useContext, useEffect, useState } from "react";
import type { User } from "@/lib/api";
import { loginApi } from "@/lib/api";
import { saveAuth, getStoredToken, getStoredUser, clearAuth } from "@/lib/auth";

interface AuthContextValue {
  user: User | null;
  login: (phone: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const token = getStoredToken();
    if (!token) return null;
    return getStoredUser();
  });

  useEffect(() => {
    function handleLogout() {
      setUser(null);
    }
    window.addEventListener("auth:logout", handleLogout);
    return () => window.removeEventListener("auth:logout", handleLogout);
  }, []);

  async function login(phone: string, password: string) {
    const response = await loginApi(phone, password);
    saveAuth(response.access_token, response.user);
    setUser(response.user);
  }

  function logout() {
    clearAuth();
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{ user, login, logout, isAuthenticated: user !== null }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
