import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { Spinner, Empty } from "../components.jsx";

const TAG = {
  pass: "ok",
  reject: "off",
  "reject-failclosed": "off",
  "reject-baduser": "off",
  "reject-nopool": "off",
  "skip-faildopen": "accent",
  "no-rule": "off",
  "no-config": "off",
  "n-a": "",
};

// ---- Decisions: structured rows from proxy_decision (what the panel proxied) --
function DecisionsTable() {
  const [rows, setRows] = useState(null);
  const [user, setUser] = useState("");

  const load = async () => {
    const q = user ? `?username=${encodeURIComponent(user)}` : "";
    setRows(await api.decisions.list(q));
  };
  useEffect(() => {
    load();
  }, []);

  if (rows === null) return <Spinner />;

  return (
    <>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginBottom: 12 }}>
        <input
          className="filter-input"
          placeholder="filter user…"
          value={user}
          onChange={(e) => setUser(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
          style={{ width: 160 }}
        />
        <button className="btn ghost" onClick={load}>Refresh</button>
      </div>
      {rows.length === 0 ? (
        <Empty>
          No decisions yet. Each proxied/gated request FreeRADIUS handles is
          recorded here. Requests it drops before routing (unknown client, bad
          secret) appear under <b>Server log</b>.
        </Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th><th>User</th><th>Realm</th><th>NAS IP</th>
                <th>Source IP</th><th>AD</th><th>Reply</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="muted mono">
                    {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                  </td>
                  <td className="mono">{r.username || "—"}</td>
                  <td className="mono muted">{r.realm || "—"}</td>
                  <td className="mono">{r.nas_ip || "—"}</td>
                  <td className="mono">{r.packet_src_ip || "—"}</td>
                  <td>
                    {r.ad_result ? (
                      <span className={`tag ${TAG[r.ad_result] || ""}`}>{r.ad_result}</span>
                    ) : "—"}
                  </td>
                  <td className="mono">{r.reply || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

// ---- Server log: raw FreeRADIUS log (what it drops BEFORE any policy runs) ----
const LEVEL_CLASS = { Error: "danger", Auth: "accent", Warn: "warn", Warning: "warn" };

function ServerLog() {
  const [data, setData] = useState(null);
  const [q, setQ] = useState("");
  const [auto, setAuto] = useState(false);
  const timer = useRef(null);

  const load = async (query = q) => {
    try {
      setData(await api.logs.radius(400, query));
    } catch (e) {
      setData({ lines: [], error: e.message });
    }
  };
  useEffect(() => {
    load("");
  }, []);
  useEffect(() => {
    if (auto) {
      timer.current = setInterval(() => load(), 4000);
      return () => clearInterval(timer.current);
    }
  }, [auto, q]);

  if (data === null) return <Spinner />;

  return (
    <>
      <p className="field-hint" style={{ margin: "0 0 12px" }}>
        Raw FreeRADIUS log — shows what the decision log can't: packets dropped
        before routing, e.g. <span className="mono">unknown client</span> (with its
        real source IP) or a bad shared secret. Read-only.
      </p>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginBottom: 12 }}>
        <input
          className="filter-input"
          placeholder="filter text (e.g. unknown, reject, 10.0.)…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
          style={{ width: 260 }}
        />
        <label className="check" style={{ margin: 0 }}>
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
          <span style={{ margin: 0 }}>auto</span>
        </label>
        <button className="btn ghost" onClick={() => load()}>Refresh</button>
      </div>
      {data.error && <div className="result err"><div className="muted">{data.error}</div></div>}
      {(!data.lines || data.lines.length === 0) ? (
        <Empty>No log lines. Send a RADIUS request to your server to see activity.</Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 170 }}>Time</th>
                <th style={{ width: 90 }}>Level</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {data.lines.map((l, i) => (
                <tr key={i}>
                  <td className="muted mono" style={{ whiteSpace: "nowrap" }}>
                    {l.ts ? new Date(l.ts).toLocaleString() : "—"}
                  </td>
                  <td>
                    {l.level ? (
                      <span className={`tag ${LEVEL_CLASS[l.level] || ""}`}>{l.level}</span>
                    ) : "—"}
                  </td>
                  <td className="mono" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                    {l.text}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

export default function Logs() {
  const [sub, setSub] = useState("decisions");
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Logs</h1>
          <p>
            <b>Decisions</b> — every request the panel proxied/gated.{" "}
            <b>Server log</b> — raw FreeRADIUS, incl. packets dropped before routing.
          </p>
        </div>
      </div>
      <div className="subtabs">
        <button
          className={`subtab ${sub === "decisions" ? "active" : ""}`}
          onClick={() => setSub("decisions")}
        >
          Decisions
        </button>
        <button
          className={`subtab ${sub === "server" ? "active" : ""}`}
          onClick={() => setSub("server")}
        >
          Server log
        </button>
      </div>
      {sub === "decisions" ? <DecisionsTable /> : <ServerLog />}
    </>
  );
}
