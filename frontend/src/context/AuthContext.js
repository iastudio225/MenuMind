import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import api, { SESSION_INVALIDATED_EVENT } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = anonymous, object = authed

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
      return data;
    } catch (e) {
      if ([401, 403].includes(e.response?.status)) {
        setUser(false);
      }
      return false;
    }
  }, []);

  useEffect(() => {
    const handleSessionInvalidated = () => setUser(false);
    window.addEventListener(SESSION_INVALIDATED_EVENT, handleSessionInvalidated);
    refresh();
    return () => window.removeEventListener(SESSION_INVALIDATED_EVENT, handleSessionInvalidated);
  }, [refresh]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setUser(data);
    return data;
  };

  const register = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    setUser(data);
    return data;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch (e) {}
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
