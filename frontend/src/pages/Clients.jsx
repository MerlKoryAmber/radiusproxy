import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Modal, Field, Spinner, Empty, StatusDot } from "../components.jsx";

const BLANK = {
  name: "",
  ipaddr: "",
  secret: "",
  shortname: "",
  nas_type: "other",
  proto: "udp",
  require_message_authenticator: "auto",
  enabled: true,
  note: "",
};

export default function Clients({ notify, onChange }) {
  const [rows, setRows] = useState(null);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(BLANK);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setRows(await api.clients.list());
  };
  useEffect(() => {
    load();
  }, []);

  const openNew = () => {
    setForm(BLANK);
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

  const save = async () => {
    setSaving(true);
    try {
      if (editing.id) {
        await api.clients.update(editing.id, form);
        notify(`Client ${form.name} updated`);
      } else {
        await api.clients.create(form);
        notify(`Client ${form.name} created`);
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

  const remove = async (r) => {
    if (!confirm(`Delete client "${r.name}"?`)) return;
    try {
      await api.clients.remove(r.id);
      notify(`Client ${r.name} deleted`);
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
          <h1>Clients</h1>
          <p>
            The request originators (NAS) allowed to send us RADIUS: VMware UAG,
            VPN servers, WiFi controllers. Each becomes a{" "}
            <span className="mono">client</span> block in{" "}
            <span className="mono">clients.conf</span>. Requests from unlisted IPs
            are dropped.
          </p>
        </div>
        <button className="btn primary" onClick={openNew}>
          Add client
        </button>
      </div>

      {rows.length === 0 ? (
        <Empty
          action={
            <button className="btn primary" onClick={openNew}>
              Add client
            </button>
          }
        >
          No clients yet. Add the NAS devices (UAG / VPN / WiFi) allowed to send
          requests.
        </Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Address / CIDR</th>
                <th>Type</th>
                <th>Msg-Auth</th>
                <th>State</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="mono">{r.name}</td>
                  <td className="mono">{r.ipaddr}</td>
                  <td>
                    <span className="tag">{r.nas_type}</span>
                  </td>
                  <td className="muted">{r.require_message_authenticator}</td>
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
          title={editing.id ? `Edit ${editing.name}` : "Add client"}
          onClose={() => setEditing(null)}
        >
          <div className="grid-2">
            <Field label="Name" hint="letters, digits, . _ -">
              <input value={form.name} onChange={set("name")} />
            </Field>
            <Field label="Short name" hint="blank → same as name">
              <input value={form.shortname} onChange={set("shortname")} />
            </Field>
          </div>
          <Field
            label="IP address / CIDR"
            hint="single IP (10.0.5.10) or subnet (10.0.5.0/24)"
          >
            <input
              value={form.ipaddr}
              onChange={set("ipaddr")}
              placeholder="10.0.5.10"
            />
          </Field>
          <Field label="Shared secret" hint="NAS ↔ proxy (separate from home_server)">
            <input
              value={form.secret}
              onChange={set("secret")}
              placeholder="testing123"
            />
          </Field>
          <div className="grid-2">
            <Field label="NAS type">
              <select value={form.nas_type} onChange={set("nas_type")}>
                <option value="other">other</option>
                <option value="cisco">cisco</option>
                <option value="juniper">juniper</option>
                <option value="mikrotik">mikrotik</option>
                <option value="aruba">aruba</option>
                <option value="ruckus">ruckus</option>
              </select>
            </Field>
            <Field label="Protocol">
              <select value={form.proto} onChange={set("proto")}>
                <option value="udp">udp</option>
                <option value="tcp">tcp</option>
                <option value="*">both (*)</option>
              </select>
            </Field>
          </div>
          <Field
            label="Require Message-Authenticator"
            hint="auto = require when present; yes hardens against BlastRADIUS"
          >
            <select
              value={form.require_message_authenticator}
              onChange={set("require_message_authenticator")}
            >
              <option value="auto">auto</option>
              <option value="yes">yes</option>
              <option value="no">no</option>
            </select>
          </Field>
          <div className="check" style={{ marginTop: 10 }}>
            <input
              id="client-enabled"
              type="checkbox"
              checked={form.enabled}
              onChange={set("enabled")}
            />
            <label htmlFor="client-enabled" style={{ margin: 0 }}>
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
    </>
  );
}
