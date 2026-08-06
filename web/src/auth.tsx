import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, registerAuth } from "./api";
import type { LabMe } from "./types";

export type AuthMode = "loading" | "local" | "deploy";
export type Route = "loading" | "login" | "onboarding" | "app";

// 게이트 분기 — 순수 함수로 분리해 테스트한다
export function resolveRoute(mode: AuthMode, session: boolean, lab: boolean): Route {
  if (mode === "loading") return "loading";
  if (mode === "local") return "app";
  if (!session) return "login";
  return lab ? "app" : "onboarding";
}

interface AuthState {
  mode: AuthMode;
  session: Session | null;
  me: LabMe | null;
  refreshLab: () => Promise<void>;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthState>({
  mode: "local", session: null, me: null,
  refreshLab: async () => {}, signIn: async () => {}, signOut: async () => {},
});
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<AuthMode>("loading");
  const [session, setSession] = useState<Session | null>(null);
  const [me, setMe] = useState<LabMe | null>(null);
  const sb = useRef<SupabaseClient | null>(null);

  async function refreshLab() {
    try {
      setMe(await api.labMe());
    } catch {
      setMe(null);   // 무소속·오류 모두 — 게이트가 온보딩으로 보낸다
    }
  }

  useEffect(() => {
    let unsub = () => {};
    void (async () => {
      try {
        const cfg = await api.authConfig();
        if (!cfg.deploy || !cfg.supabase_url || !cfg.supabase_anon_key) {
          setMode("local");
          return;
        }
        const client = createClient(cfg.supabase_url, cfg.supabase_anon_key);
        sb.current = client;
        registerAuth(
          async () => (await client.auth.getSession()).data.session?.access_token ?? null,
          (status) => { if (status === 401) void client.auth.signOut(); },
        );
        const { data } = await client.auth.getSession();
        setSession(data.session);
        setMode("deploy");
        const sub = client.auth.onAuthStateChange((_e, s) => setSession(s));
        unsub = () => sub.data.subscription.unsubscribe();
      } catch {
        setMode("local");   // auth-config가 없는 구버전 서버 — 기존 동작 유지
      }
    })();
    return () => unsub();   // 구독은 async 완료 후에 대입되므로 호출을 감싼다
  }, []);

  useEffect(() => {
    if (mode === "deploy" && session) void refreshLab();
    if (!session) setMe(null);
  }, [mode, session]);

  return (
    <Ctx.Provider value={{
      mode, session, me, refreshLab,
      signIn: async () => {
        await sb.current?.auth.signInWithOAuth({
          provider: "google", options: { redirectTo: window.location.origin },
        });
      },
      signOut: async () => { await sb.current?.auth.signOut(); },
    }}>
      {children}
    </Ctx.Provider>
  );
}
