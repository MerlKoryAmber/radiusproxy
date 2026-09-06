import { useEffect, useState, useCallback } from "react";
import { api } from "./api.js";
import HomeServers from "./pages/HomeServers.jsx";
import Pools from "./pages/Pools.jsx";
import Realms from "./pages/Realms.jsx";
import LdapSettings from "./pages/LdapSettings.jsx";
import ConfigPreview from "./pages/ConfigPreview.jsx";

const TABS = [
  { id: "home-servers", label: "Home servers" },
  { id: "pools", label: "Pools" },
  { id: "realms", label: "Realms" },
  { id: "ldap", label: "AD / LDAP" },
  { id: "config", label: "Config & apply" },
];

export default function App() {
  const [tab, setTab] = useState("home-servers");
  const [toast, setToast] = useState(null);
  const [counts, setCounts] = useState({});

  const notify = useCallback((message, kind = "ok") => {
    setToast({ message, kind });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const refreshCounts = useCallback(async () => {
    try {
      const [hs, pools, realms] = await Promise.all([
        api.homeServers.list(),
        api.pools.list(),
        api.realms.list(),
      ]);
      setCounts({
        "home-servers": hs.length,
        pools: pools.length,
        realms: realms.length,
      });
    } catch {
      /* backend not up yet — counts stay empty */
    }
  }, []);

  useEffect(() => {
    refreshCounts();
  }, [refreshCounts, tab]);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="dot" />
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
              {counts[t.id] != null && t.id !== "config" && (
                <span className="count">{counts[t.id]}</span>
              )}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main">
        {tab === "home-servers" && (
          <HomeServers notify={notify} onChange={refreshCounts} />
        )}
        {tab === "pools" && <Pools notify={notify} onChange={refreshCounts} />}
        {tab === "realms" && <Realms notify={notify} onChange={refreshCounts} />}
        {tab === "ldap" && <LdapSettings notify={notify} />}
        {tab === "config" && <ConfigPreview notify={notify} />}
      </main>

      {toast && (
        <div className={`toast ${toast.kind === "err" ? "err" : ""}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
