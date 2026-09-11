import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Spinner, Empty } from "../components.jsx";

const TAG = {
  pass: "ok",
  reject: "off",
  "reject-failclosed": "off",
  "skip-faildopen": "accent",
  "n-a": "",
};

export default function Decisions() {
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
      <div className="page-head">
        <div>
          <h1>Logs</h1>
          <p>
            Per-request proxy/gate decisions written by FreeRADIUS (the{" "}
            <span className="mono">radiuspanel_log</span> policy) into the panel
            database.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            className="filter-input"
            placeholder="filter user…"
            value={user}
            onChange={(e) => setUser(e.target.value)}
            style={{ width: 160 }}
          />
          <button className="btn ghost" onClick={load}>
            Refresh
          </button>
        </div>
      </div>

      {rows.length === 0 ? (
        <Empty>
          No decisions logged yet. Wire <span className="mono">radiuspanel_log</span>{" "}
          into your site's post-auth to start recording.
        </Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>User</th>
                <th>Realm</th>
                <th>NAS IP</th>
                <th>Source IP</th>
                <th>AD</th>
                <th>Reply</th>
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
                      <span className={`tag ${TAG[r.ad_result] || ""}`}>
                        {r.ad_result}
                      </span>
                    ) : (
                      "—"
                    )}
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
