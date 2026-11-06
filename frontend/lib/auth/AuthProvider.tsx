"use client";

import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { ApiError } from "@/lib/api/client";
import * as auth from "@/lib/api/auth";

type AuthState = {
  me: auth.Me | null;
  loading: boolean;
  refresh: () => Promise<void>;
  setMe: (me: auth.Me | null) => void;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState>({
  me: null,
  loading: true,
  refresh: async () => {},
  setMe: () => {},
  signOut: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<auth.Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setMe((await auth.getSession()).user);
    } catch (e) {
      if (!(e instanceof ApiError)) console.warn(e);
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signOut = useCallback(async () => {
    await auth.logout();
    setMe(null);
  }, []);

  return <AuthContext.Provider value={{ me, loading, refresh, setMe, signOut }}>{children}</AuthContext.Provider>;
}
