"use client";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  useMemo,
  ReactNode,
} from "react";
import { createClient } from "@/utils/supabase/client";
import type { OAuthResponse, User } from "@supabase/supabase-js";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  loginWithGoogle: () => Promise<OAuthResponse>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const supabase = useMemo(() => createClient(), []);

  // Only swaps the `user` object in state when the underlying user id
  // actually changes. Supabase re-emits onAuthStateChange (e.g. on tab
  // visibility/focus, token refresh) with a freshly deserialized user
  // object even when it's the same signed-in user.
  const applyUser = (nextUser: User | null) => {
    setUser((prevUser) => {
      if (prevUser?.id === (nextUser?.id ?? null)) {
        return prevUser;
      }
      return nextUser ?? null;
    });
  };

  useEffect(() => {
    const getInitialUser = async () => {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      applyUser(user);
      setLoading(false);
    };

    getInitialUser();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      applyUser(session?.user ?? null);
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, [supabase]);

  const loginWithGoogle = async () => {
    return supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
  };

  const logout = async (): Promise<void> => {
    await supabase.auth.signOut();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, loginWithGoogle, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}