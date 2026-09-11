import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Modal, Field, Spinner, Empty, StatusDot, ConfirmDialog } from "../components.jsx";

const BLANK = {
  name: "",
  type: "auth+acct",
  ipaddr: "",
  port: 1812,
  secret: "",
  status_check: "status-server",
  require_message_authenticator: false,
  response_window: 20,
  zombie_period: 40,
  revive_interval: 120,
  check_interval: 30,
  enabled: true,
  note: "",
};

export default function TargetServers({ notify, onChange }) {
  const [rows, setRows] = useState(null);
  const [editing, setEditing] = useState(null); // object or null
  const [pendingDel, setPendingDel] = useState(null);
  const [form, setForm] = useState(BLANK);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setRows(await api.targetServers.list());
  };
  useEffect(() => {
    load();
  }, []);

  const openNew = () => {
    setForm(BLANK);
    setEditing({});
  };
  const openEdit = (r) => {
    setForm({ ...BLANK, ...r, secret: "" });
    setEditing(r);
  };

  const set = (k) => (e) => {
    const v =
      e.target.type === "checkbox"
        ? e.target.checked
        : e.target.type === "number"
        ? Number(e.target.value)
        : e.target.value;
    setForm((f) => ({ ...f, [k]: v }));
  };

  const save = async () => {
    setSaving(true);
    try {
      if (editing.id) {
        await api.targetServers.update(editing.id, form);
        notify(`Target server ${form.name} updated`);
      } else {
        await api.targetServers.create(form);
        notify(`Target server ${form.name} created`);
      }
      setEditing(null);
      await load();
      onChange?.();
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
      await api.targetServers.remove(r.id);
      notify(`Target server ${r.name} deleted`);
      await load();
      onChange?.();
    } catch (e) {
      notify(e.message, "err");
    }
  };

  if (rows === null) return <Spinner />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Target servers</h1>
          <p>
            Upstream RADIUS servers requests are proxied to. Each becomes a{" "}
            <span className="mono">home_server</span> block.
          </p>
        </div>
        <button className="btn primary" onClick={openNew}>
          Add target server
        </button>
      </div>

      {rows.length === 0 ? (
        <Empty
          action={
            <button className="btn primary" onClick={openNew}>
              Add target server
            </button>
          }
        >
          No target servers yet. Add the upstream servers you want to proxy to.
        </Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Address</th>
                <th>Status check</th>
                <th>State</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="mono">{r.name}</td>
                  <td>
                    <span className="tag">{r.type}</span>
                  </td>
                  <td className="mono">
                    {r.ipaddr}:{r.port}
                  </td>
                  <td className="muted">{r.status_check}</td>
                  <td>
                    <StatusDot on={r.enabled} />
                    {r.enabled ? "enabled" : "disabled"}
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
          title={editing.id ? `Edit ${editing.name}` : "Add target server"}
          onClose={() => setEditing(null)}
        >
          <div className="grid-2">
            <Field label="Name" hint="letters, digits, . _ -">
              <input value={form.name} onChange={set("name")} />
            </Field>
            <Field label="Type">
              <select value={form.type} onChange={set("type")}>
                <option value="auth">auth</option>
                <option value="acct">acct</option>
                <option value="auth+acct">auth+acct</option>
                <option value="coa">coa</option>
              </select>
            </Field>
          </div>
          <div className="grid-2">
            <Field label="IP address / host">
              <input
                value={form.ipaddr}
                onChange={set("ipaddr")}
                placeholder="10.0.0.11"
              />
            </Field>
            <Field
              label="Port"
              hint={
                form.type === "auth+acct" ? "acct uses port + 1" : undefined
              }
            >
              <input type="number" value={form.port} onChange={set("port")} />
            </Field>
          </div>
          <Field
            label="Shared secret"
            hint={editing.id ? "leave blank to keep the stored secret" : undefined}
          >
            <input
              type="password"
              value={form.secret}
              onChange={set("secret")}
              placeholder={editing.id ? "•••••••• (unchanged)" : "testing123"}
            />
          </Field>
          <div className="grid-2">
            <Field label="Status check">
              <select value={form.status_check} onChange={set("status_check")}>
                <option value="status-server">status-server</option>
                <option value="request">request</option>
                <option value="none">none</option>
              </select>
            </Field>
            <Field label="Response window (s)">
              <input
                type="number"
                value={form.response_window}
                onChange={set("response_window")}
              />
            </Field>
          </div>
          <div className="grid-2">
            <Field label="Zombie period (s)">
              <input
                type="number"
                value={form.zombie_period}
                onChange={set("zombie_period")}
              />
            </Field>
            <Field label="Revive interval (s)">
              <input
                type="number"
                value={form.revive_interval}
                onChange={set("revive_interval")}
              />
            </Field>
          </div>
          <div className="check">
            <input
              id="reqmsg"
              type="checkbox"
              checked={form.require_message_authenticator}
              onChange={set("require_message_authenticator")}
            />
            <label htmlFor="reqmsg" style={{ margin: 0 }}>
              Require Message-Authenticator
            </label>
          </div>
          <div className="check" style={{ marginTop: 10 }}>
            <input
              id="enabled"
              type="checkbox"
              checked={form.enabled}
              onChange={set("enabled")}
            />
            <label htmlFor="enabled" style={{ margin: 0 }}>
              Enabled (included in generated config)
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
          title="Delete target server"
          message={`Delete target server "${pendingDel.name}"? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          onConfirm={doRemove}
          onClose={() => setPendingDel(null)}
        />
      )}
    </>
  );
}
