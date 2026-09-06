import { useEffect, useState, useCallback } from "react";
import { api, setToken } from "./api.js";
import { UserMenu } from "./components.jsx";
import Clients from "./pages/Clients.jsx";
import TargetServers from "./pages/TargetServers.jsx";
import Pools from "./pages/Pools.jsx";
import LdapSettings from "./pages/LdapSettings.jsx";
import Decisions from "./pages/Decisions.jsx";
import ConfigPreview from "./pages/ConfigPreview.jsx";
import Settings from "./pages/Settings.jsx";
import Login from "./pages/Login.jsx";

const TABS = [
  { id: "clients", label: "Clients" },
  { id: "targets", label: "Target servers" },
  { id: "pools", label: "Pools" },
  { id: "ldap", label: "AD / LDAP" },
  { id: "decisions", label: "Decision log" },
  { id: "config", label: "Config & apply" },
  { id: "settings", label: "Settings" },
];

export default function App() {
  const [tab, setTab] = useState("clients");
  const [toast, setToast] = useState(null);
  const [counts, setCounts] = useState({});
  const [authState, setAuthState] = useState("checking"); // checking | ok | login
  const [authInfo, setAuthInfo] = useState({ auth_enabled: false, user: null });

  const notify = useCallback((message, kind = "ok") => {
    setToast({ message, kind });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const checkAuth = useCallback(async () => {
    try {
      const s = await api.auth.status();
      setAuthInfo(s);
      setAuthState("ok");
    } catch (e) {
      if (e.message === "unauthorized") setAuthState("login");
      else setAuthState("ok");
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const refreshCounts = useCallback(async () => {
    try {
      const [clients, ts, pools] = await Promise.all([
        api.clients.list(),
        api.targetServers.list(),
        api.pools.list(),
      ]);
      setCounts({
        clients: clients.length,
        targets: ts.length,
        pools: pools.length,
      });
    } catch {
      /* backend not up yet — counts stay empty */
    }
  }, []);

  useEffect(() => {
    if (authState === "ok") refreshCounts();
  }, [refreshCounts, tab, authState]);

  const logout = () => {
    setToken("");
    checkAuth();
  };

  if (authState === "checking") return null;
  if (authState === "login")
    return <Login onLoggedIn={checkAuth} />;

  const currentLabel = TABS.find((t) => t.id === tab)?.label || "";
  const username = authInfo.user || "admin";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <img src="/logo.png" alt="" />
          </span>
          <b>RADIUS Proxy</b>
          <span>3.2</span>
        </div>
        <nav className="nav">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? "active" : ""}
              onClick={() => setTab(t.id)}
            >
              <span>{t.label}</span>
              {counts[t.id] != null && (
                <span className="count">{counts[t.id]}</span>
              )}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main-area">
        <div className="topbar">
          <div className="topbar-title">{currentLabel}</div>
          <UserMenu
            username={username}
            authEnabled={authInfo.auth_enabled}
            onLogout={logout}
          />
        </div>

        <div className="content">
          {tab === "clients" && (
            <Clients notify={notify} onChange={refreshCounts} />
          )}
          {tab === "targets" && (
            <TargetServers notify={notify} onChange={refreshCounts} />
          )}
          {tab === "pools" && <Pools notify={notify} onChange={refreshCounts} />}
          {tab === "ldap" && <LdapSettings notify={notify} />}
          {tab === "decisions" && <Decisions />}
          {tab === "config" && <ConfigPreview notify={notify} />}
          {tab === "settings" && (
            <Settings notify={notify} onAuthChange={checkAuth} />
          )}
        </div>
      </main>

      {toast && (
        <div className={`toast ${toast.kind === "err" ? "err" : ""}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
