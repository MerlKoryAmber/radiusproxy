import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Spinner } from "../components.jsx";

function Stat({ label, value }) {
  return (
    <div className="card">
      <b>{value}</b>
      <span className="muted">{label}</span>
    </div>
  );
}

function Pill({ ok, label, warn }) {
  const cls = ok ? "ok" : warn ? "" : "bad";
  return <span className={`tag ${ok ? "ok" : warn ? "accent" : "off"}`}>{label}</span>;
}

export default function Dashboard() {
  const [d, setD] = useState(null);

  const load = async () => setD(await api.dashboard.get());
  useEffect(() => {
    load();
  }, []);

  if (d === null) return <Spinner />;

  const sec = d.security;
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p>Overview of routing config, AD sync, and panel security.</p>
        </div>
        <button className="btn ghost" onClick={load}>
          Refresh
        </button>
      </div>

      <div className="cards cards-4">
        <Stat label="Clients" value={d.counts.clients} />
        <Stat label="Target servers" value={d.counts.targets} />
        <Stat label="Pools" value={d.counts.pools} />
        <Stat label="Rules" value={d.counts.rules} />
      </div>

      <div className="dash-grid">
        <div className="config-pane">
          <header><span>Service</span></header>
          <div className="dash-body">
            <div className="dash-row">
              <span>FreeRADIUS</span>
              <Pill ok={d.freeradius_running} label={d.freeradius_running ? "running" : "stopped"} />
            </div>
            <div className="dash-row">
              <span>Last apply</span>
              <span className="muted mono">
                {d.last_apply ? d.last_apply.detail : "never"}
              </span>
            </div>
            <div className="dash-row">
              <span>HTTPS cert</span>
              <Pill ok={!sec.tls_self_signed} warn={sec.tls_self_signed}
                label={sec.tls_self_signed ? "self-signed" : "custom"} />
            </div>
            <div className="dash-row">
              <span>Login required</span>
              <Pill ok={sec.auth_enabled} warn={!sec.auth_enabled}
                label={sec.auth_enabled ? "on" : "off"} />
            </div>
            <div className="dash-row">
              <span>IP restriction</span>
              <Pill ok={sec.ip_restricted} warn={!sec.ip_restricted}
                label={sec.ip_restricted ? "on" : "off"} />
            </div>
          </div>
        </div>

        <div className="config-pane">
          <header><span>Active Directory</span></header>
          <div className="dash-body">
            <div className="dash-row">
              <span>AD gate</span>
              <Pill ok={d.ad.enabled} warn={!d.ad.enabled} label={d.ad.enabled ? "enabled" : "off"} />
            </div>
            <div className="dash-row"><span>Group catalog</span><span className="mono">{d.ad.catalog}</span></div>
            <div className="dash-row"><span>Synced members</span><span className="mono">{d.ad.members}</span></div>
            <div className="dash-row">
              <span>Group sync</span>
              <span className="mono">
                {d.ad.groups_ok} ok{d.ad.groups_error ? `, ${d.ad.groups_error} error` : ""}
              </span>
            </div>
            <div className="dash-row">
              <span>Last sync</span>
              <span className="muted mono">
                {d.ad.last_sync ? new Date(d.ad.last_sync).toLocaleString() : "never"}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="section-heading" style={{ margin: "18px 0 8px", fontWeight: 600 }}>
        Recent decisions
      </div>
      {d.recent_decisions.length === 0 ? (
        <div className="empty" style={{ padding: 20 }}>
          No decisions yet (needs RADIUS traffic + the log policy wired in).
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Time</th><th>User</th><th>Realm</th><th>AD</th><th>Reply</th></tr>
            </thead>
            <tbody>
              {d.recent_decisions.map((r, i) => (
                <tr key={i}>
                  <td className="muted mono">{r.at ? new Date(r.at).toLocaleString() : "—"}</td>
                  <td className="mono">{r.username || "—"}</td>
                  <td className="mono muted">{r.realm || "—"}</td>
                  <td className="mono">{r.ad_result || "—"}</td>
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
