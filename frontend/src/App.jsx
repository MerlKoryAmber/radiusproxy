import { useEffect, useState, useCallback } from "react";
import { api, setToken } from "./api.js";
import { UserMenu } from "./components.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Clients from "./pages/Clients.jsx";
import TargetServers from "./pages/TargetServers.jsx";
import Pools from "./pages/Pools.jsx";
import Rules from "./pages/Rules.jsx";
import Decisions from "./pages/Decisions.jsx";
import ConfigPreview from "./pages/ConfigPreview.jsx";
import Portable from "./pages/Portable.jsx";
import Settings from "./pages/Settings.jsx";
import Help from "./pages/Help.jsx";
import Login from "./pages/Login.jsx";

const TABS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "clients", label: "Clients" },
  { id: "targets", label: "Target servers" },
  { id: "pools", label: "Pools" },
  { id: "rules", label: "Rules" },
  { id: "decisions", label: "Logs" },
  { id: "config", label: "Config & apply" },
  { id: "portable", label: "Import / Export" },
  { id: "settings", label: "Settings" },
];

const TAB_IDS = TABS.map((t) => t.id);
const savedTab = () => {
  try {
    const t = localStorage.getItem("radpanel_tab");
    return TAB_IDS.includes(t) ? t : "dashboard";
  } catch {
    return "dashboard";
  }
};

export default function App() {
  // Persist the open tab so F5 / reload stays put instead of snapping back to
  // Dashboard.
  const [tab, setTab] = useState(savedTab);
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

  useEffect(() => {
    try {
      localStorage.setItem("radpanel_tab", tab);
    } catch {
      /* storage unavailable — tab just won't persist */
    }
  }, [tab]);

  const refreshCounts = useCallback(async () => {
    try {
      const [clients, ts, pools, rules] = await Promise.all([
        api.clients.list(),
        api.targetServers.list(),
        api.pools.list(),
        api.rules.list(),
      ]);
      setCounts({
        clients: clients.length,
        targets: ts.length,
        pools: pools.length,
        rules: rules.length,
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

  const currentLabel =
    tab === "help" ? "Инструкция" : TABS.find((t) => t.id === tab)?.label || "";
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
          <button
            className={tab === "help" ? "active" : ""}
            style={{ marginTop: "auto" }}
            onClick={() => setTab("help")}
          >
            <span>Инструкция</span>
          </button>
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
          {tab === "dashboard" && <Dashboard />}
          {tab === "clients" && (
            <Clients notify={notify} onChange={refreshCounts} />
          )}
          {tab === "targets" && (
            <TargetServers notify={notify} onChange={refreshCounts} />
          )}
          {tab === "pools" && <Pools notify={notify} onChange={refreshCounts} />}
          {tab === "rules" && <Rules notify={notify} />}
          {tab === "decisions" && <Decisions />}
          {tab === "config" && <ConfigPreview notify={notify} />}
          {tab === "portable" && (
            <Portable notify={notify} onChange={refreshCounts} />
          )}
          {tab === "settings" && (
            <Settings notify={notify} onAuthChange={checkAuth} />
          )}
          {tab === "help" && <Help />}
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
