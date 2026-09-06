import { useEffect, useState, useCallback } from "react";
import { api } from "./api.js";
import Clients from "./pages/Clients.jsx";
import HomeServers from "./pages/HomeServers.jsx";
import Pools from "./pages/Pools.jsx";
import Realms from "./pages/Realms.jsx";
import LdapSettings from "./pages/LdapSettings.jsx";
import Decisions from "./pages/Decisions.jsx";
import ConfigPreview from "./pages/ConfigPreview.jsx";
import Access from "./pages/Access.jsx";
import Login from "./pages/Login.jsx";

const TABS = [
  { id: "clients", label: "Clients" },
  { id: "home-servers", label: "Home servers" },
  { id: "pools", label: "Pools" },
  { id: "realms", label: "Realms" },
  { id: "ldap", label: "AD / LDAP" },
  { id: "decisions", label: "Decision log" },
  { id: "config", label: "Config & apply" },
  { id: "access", label: "Access" },
];

export default function App() {
  const [tab, setTab] = useState("clients");
  const [toast, setToast] = useState(null);
  const [counts, setCounts] = useState({});
  const [authState, setAuthState] = useState("checking"); // checking | ok | login

  const notify = useCallback((message, kind = "ok") => {
    setToast({ message, kind });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const checkAuth = useCallback(async () => {
    try {
      await api.auth.status();
      setAuthState("ok");
    } catch (e) {
      setAuthState(e.message === "unauthorized" ? "login" : "ok");
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const refreshCounts = useCallback(async () => {
    try {
      const [clients, hs, pools, realms] = await Promise.all([
        api.clients.list(),
        api.homeServers.list(),
        api.pools.list(),
        api.realms.list(),
      ]);
      setCounts({
        clients: clients.length,
        "home-servers": hs.length,
        pools: pools.length,
        realms: realms.length,
      });
    } catch {
      /* backend not up yet — counts stay empty */
    }
  }, []);

  useEffect(() => {
    if (authState === "ok") refreshCounts();
  }, [refreshCounts, tab, authState]);

  if (authState === "checking") return null;
  if (authState === "login")
    return <Login onLoggedIn={() => setAuthState("ok")} />;

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

      <main className="main">
        {tab === "clients" && (
          <Clients notify={notify} onChange={refreshCounts} />
        )}
        {tab === "home-servers" && (
          <HomeServers notify={notify} onChange={refreshCounts} />
        )}
        {tab === "pools" && <Pools notify={notify} onChange={refreshCounts} />}
        {tab === "realms" && <Realms notify={notify} onChange={refreshCounts} />}
        {tab === "ldap" && <LdapSettings notify={notify} />}
        {tab === "decisions" && <Decisions />}
        {tab === "config" && <ConfigPreview notify={notify} />}
        {tab === "access" && (
          <Access notify={notify} onAuthChange={checkAuth} />
        )}
      </main>

      {toast && (
        <div className={`toast ${toast.kind === "err" ? "err" : ""}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
