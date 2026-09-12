import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { Modal, Field, Spinner, Empty, StatusDot, ConfirmDialog } from "../components.jsx";

const BLANK = {
  name: "",
  client_id: null,
  match_username: "",
  target_pool_id: null,
  ad_group_check: false,
  required_ad_group: "",
  required_ad_group_dn: "",
  username_normalization: "none",
  ad_fail_mode: "open",
  pool_down_fallback: false,
  enabled: true,
  note: "",
};

// Group name autocomplete backed by the synced AD catalog.
function GroupPicker({ value, onPick }) {
  const [q, setQ] = useState(value || "");
  const [opts, setOpts] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => setQ(value || ""), [value]);
  useEffect(() => {
    const onDoc = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const search = async (text) => {
    setQ(text);
    onPick(text, ""); // typed name, dn unknown until a pick
    try {
      setOpts(await api.ldap.groups(text));
      setOpen(true);
    } catch {
      setOpts([]);
    }
  };

  return (
    <div style={{ position: "relative" }} ref={ref}>
      <input
        value={q}
        onChange={(e) => search(e.target.value)}
        onFocus={() => q && search(q)}
        placeholder="start typing a group name…"
      />
      {open && opts.length > 0 && (
        <div className="user-menu-dropdown" style={{ left: 0, right: 0, maxHeight: 220, overflow: "auto" }}>
          {opts.map((g) => (
            <button
              key={g.dn}
              className="user-menu-item"
              onClick={() => {
                onPick(g.cn, g.dn);
                setQ(g.cn);
                setOpen(false);
              }}
              title={g.dn}
            >
              <div>{g.cn}</div>
              <div className="muted" style={{ fontSize: 11 }}>{g.dn}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Rules({ notify }) {
  const [rows, setRows] = useState(null);
  const [clients, setClients] = useState([]);
  const [pools, setPools] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(BLANK);
  const [saving, setSaving] = useState(false);
  const [pendingDel, setPendingDel] = useState(null);

  const load = async () => {
    const [r, c, p] = await Promise.all([
      api.rules.list(),
      api.clients.list(),
      api.pools.list(),
    ]);
    setRows(r);
    setClients(c);
    setPools(p);
  };
  useEffect(() => {
    load();
  }, []);

  const openNew = () => {
    setForm({ ...BLANK, client_id: clients[0]?.id ?? null });
    setEditing({});
  };
  const openEdit = (r) => {
    setForm({ ...BLANK, ...r });
    setEditing(r);
  };

  const set = (k) => (e) => {
    const v = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [k]: v }));
  };
  const setNum = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e.target.value === "" ? null : Number(e.target.value) }));

  const save = async () => {
    setSaving(true);
    try {
      if (!form.client_id) throw new Error("pick a client");
      if (editing.id) await api.rules.update(editing.id, form);
      else await api.rules.create(form);
      notify("Rule saved");
      setEditing(null);
      await load();
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setSaving(false);
    }
  };

  const remove = (r) => setPendingDel(r);
  const doRemove = async () => {
    const r = pendingDel;
    setPendingDel(null);
    try {
      await api.rules.remove(r.id);
      await load();
    } catch (e) {
      notify(e.message, "err");
    }
  };

  const move = async (idx, dir) => {
    const ids = rows.map((r) => r.id);
    const j = idx + dir;
    if (j < 0 || j >= ids.length) return;
    [ids[idx], ids[j]] = [ids[j], ids[idx]];
    setRows(dir === -1 ? swap(rows, idx, j) : swap(rows, idx, j));
    try {
      await api.rules.reorder(ids);
      await load();
    } catch (e) {
      notify(e.message, "err");
      await load();
    }
  };

  if (rows === null) return <Spinner />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Rules</h1>
          <p>
            Routing rules, evaluated top → bottom — first match wins. A rule
            matches a client (optionally a username wildcard), proxies to a pool,
            and can require an AD group. No rule matches → request is rejected.
          </p>
        </div>
        <button className="btn primary" onClick={openNew} disabled={clients.length === 0}>
          Add rule
        </button>
      </div>

      {clients.length === 0 && (
        <div className="empty" style={{ marginBottom: 16 }}>
          Add a client first — rules route from a client to a pool.
        </div>
      )}

      {rows.length === 0 ? (
        <Empty>No rules yet. Add one to start proxying.</Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 64 }}>Order</th>
                <th>Name</th>
                <th>Client</th>
                <th>Username</th>
                <th>Target pool</th>
                <th>AD group</th>
                <th>State</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, idx) => (
                <tr key={r.id}>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button className="move" onClick={() => move(idx, -1)} title="Up">
                      ↑
                    </button>
                    <button className="move" onClick={() => move(idx, 1)} title="Down">
                      ↓
                    </button>
                  </td>
                  <td>{r.name || <span className="muted">#{r.id}</span>}</td>
                  <td className="mono">{r.client_name || "—"}</td>
                  <td className="mono muted">{r.match_username || "any"}</td>
                  <td className="mono">{r.target_pool_name || "—"}</td>
                  <td>
                    {r.ad_group_check ? (
                      <span className="tag accent" title={r.required_ad_group_dn}>
                        {r.required_ad_group || "?"}
                      </span>
                    ) : (
                      <span className="tag off">—</span>
                    )}
                  </td>
                  <td>
                    <StatusDot on={r.enabled} />
                    {r.enabled ? "on" : "off"}
                  </td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="btn sm ghost" onClick={() => openEdit(r)}>
                      Edit
                    </button>
                    <button className="btn danger" onClick={() => remove(r)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <Modal
          title={editing.id ? `Edit rule` : "Add rule"}
          onClose={() => setEditing(null)}
        >
          <Field label="Name" hint="optional label">
            <input value={form.name} onChange={set("name")} />
          </Field>
          <div className="grid-2">
            <Field label="Client">
              <select value={form.client_id ?? ""} onChange={setNum("client_id")}>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Username match" hint="blank = any; wildcard e.g. *@corp">
              <input
                value={form.match_username}
                onChange={set("match_username")}
                placeholder="*"
              />
            </Field>
          </div>
          <Field label="Target pool" hint="where matching requests are proxied">
            <select value={form.target_pool_id ?? ""} onChange={setNum("target_pool_id")}>
              <option value="">— none (reject) —</option>
              {pools.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>

          <div className="check" style={{ marginTop: 10 }}>
            <input
              id="rule-ad"
              type="checkbox"
              checked={form.ad_group_check}
              onChange={set("ad_group_check")}
            />
            <label htmlFor="rule-ad" style={{ margin: 0 }}>
              Require AD group membership
            </label>
          </div>
          {form.ad_group_check && (
            <>
              <Field label="AD group" hint="type the group name; picked from synced catalog">
                <GroupPicker
                  value={form.required_ad_group}
                  onPick={(cn, dn) =>
                    setForm((f) => ({
                      ...f,
                      required_ad_group: cn,
                      required_ad_group_dn: dn,
                    }))
                  }
                />
              </Field>
              <div className="grid-2">
                <Field label="Username sent to AD">
                  <select
                    value={form.username_normalization}
                    onChange={set("username_normalization")}
                  >
                    <option value="none">as received</option>
                    <option value="strip_realm">strip @realm → user</option>
                    <option value="strip_ntdomain">DOMAIN\\user → user</option>
                  </select>
                </Field>
                <Field label="If AD list unavailable" hint="open = proxy; closed = reject">
                  <select value={form.ad_fail_mode} onChange={set("ad_fail_mode")}>
                    <option value="open">fail-open</option>
                    <option value="closed">fail-closed</option>
                  </select>
                </Field>
              </div>
            </>
          )}

          <div className="check" style={{ marginTop: 10 }}>
            <input
              id="rule-fallback"
              type="checkbox"
              checked={form.pool_down_fallback}
              onChange={set("pool_down_fallback")}
            />
            <label htmlFor="rule-fallback" style={{ margin: 0 }}>
              При недоступности пула — пускать по паролю AD (обход 2FA)
            </label>
          </div>
          {form.pool_down_fallback && (
            <p className="field-hint" style={{ color: "var(--warn)", marginTop: 6 }}>
              ⚠ Если целевой пул (2FA) полностью недоступен, панель проверит только
              1-й фактор (пароль в AD, PAP) и <b>впустит</b> — это осознанный обход
              2FA на время аварии. Требует настроенного AD/LDAP. Такие входы
              помечаются в Logs как <span className="mono">pool-down-1fa</span>.
            </p>
          )}

          <div className="check" style={{ marginTop: 10 }}>
            <input
              id="rule-enabled"
              type="checkbox"
              checked={form.enabled}
              onChange={set("enabled")}
            />
            <label htmlFor="rule-enabled" style={{ margin: 0 }}>
              Enabled
            </label>
          </div>

          <div className="modal-actions">
            <button className="btn ghost" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button className="btn primary" disabled={saving} onClick={save}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </Modal>
      )}
      {pendingDel && (
        <ConfirmDialog
          title="Delete rule"
          message={`Delete rule "${pendingDel.name || "#" + pendingDel.id}"? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          onConfirm={doRemove}
          onClose={() => setPendingDel(null)}
        />
      )}
    </>
  );
}

function swap(arr, i, j) {
  const a = [...arr];
  [a[i], a[j]] = [a[j], a[i]];
  return a;
}
