import { createContext, useCallback, useContext, useMemo, useState } from "react";
import api from "../api/client";

const AuthContext = createContext(null);

function readStoredUser() {
  try {
    const token = localStorage.getItem("token");
    const user = JSON.parse(localStorage.getItem("user"));
    return token && user ? user : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUserState] = useState(readStoredUser);

  const setUser = useCallback((next) => {
    setUserState(next);
    if (next) localStorage.setItem("user", JSON.stringify(next));
    else localStorage.removeItem("user");
  }, []);

  const saveSession = useCallback(
    ({ token, user: u }) => {
      localStorage.setItem("token", token);
      setUser(u);
      return u;
    },
    [setUser]
  );

  const login = useCallback(
    (email, password) => api.post("/api/auth/login", { email, password }).then((r) => saveSession(r.data)),
    [saveSession]
  );

  const register = useCallback(
    (name, email, password) =>
      api.post("/api/auth/register", { name, email, password }).then((r) => saveSession(r.data)),
    [saveSession]
  );

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    setUser(null);
  }, [setUser]);

  const value = useMemo(() => ({ user, setUser, login, register, logout }), [user, setUser, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
