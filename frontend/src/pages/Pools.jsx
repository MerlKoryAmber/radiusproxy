import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Modal, Field, Spinner, Empty, StatusDot } from "../components.jsx";

const BLANK = { name: "", type: "fail-over", enabled: true, note: "", member_ids: [] };

const POOL_TYPES = [
  "fail-over",
  "load-balance",
  "client-balance",
  "client-port-balance",
  "keyed-balance",
];

export default function Pools({ notify, onChange }) {
  const [rows, setRows] = useState(null);
  const [servers, setServers] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(BLANK);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const [pools, ts] = await Promise.all([
      api.pools.list(),
      api.targetServers.list(),
    ]);
    setRows(pools);
    setServers(ts);
  };
  useEffect(() => {
    load();
  }, []);

  const serverName = (id) => servers.find((s) => s.id === id)?.name ?? `#${id}`;

  const openNew = () => {
    setForm(BLANK);
    setEditing({});
  };
  const openEdit = (p) => {
    setForm({
      name: p.name,
      type: p.type,
      enabled: p.enabled,
      note: p.note || "",
      member_ids: p.members.map((m) => m.target_server_id),
    });
    setEditing(p);
  };

  const set = (k) => (e) => {
    const v = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [k]: v }));
  };

  const addMember = () => {
    const avail = servers.find((s) => !form.member_ids.includes(s.id));
    if (!avail) return;
    setForm((f) => ({ ...f, member_ids: [...f.member_ids, avail.id] }));
  };
  const setMember = (idx, id) =>
    setForm((f) => {
      const m = [...f.member_ids];
      m[idx] = Number(id);
      return { ...f, member_ids: m };
    });
  const moveMember = (idx, dir) =>
    setForm((f) => {
      const m = [...f.member_ids];
      const j = idx + dir;
      if (j < 0 || j >= m.length) return f;
      [m[idx], m[j]] = [m[j], m[idx]];
      return { ...f, member_ids: m };
    });
  const removeMember = (idx) =>
    setForm((f) => ({
      ...f,
      member_ids: f.member_ids.filter((_, i) => i !== idx),
    }));

  const save = async () => {
    setSaving(true);
    try {
      if (editing.id) {
        await api.pools.update(editing.id, form);
        notify(`Pool ${form.name} updated`);
      } else {
        await api.pools.create(form);
        notify(`Pool ${form.name} created`);
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

  const remove = async (p) => {
    if (!confirm(`Delete pool "${p.name}"?`)) return;
    try {
      await api.pools.remove(p.id);
      notify(`Pool ${p.name} deleted`);
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
          <h1>Pools</h1>
          <p>
            Groups of target servers with a load-balancing strategy. For{" "}
            <span className="mono">fail-over</span>, order is priority — first
            listed is primary.
          </p>
        </div>
        <button className="btn primary" onClick={openNew}>
          Add pool
        </button>
      </div>

      {rows.length === 0 ? (
        <Empty
          action={
            <button className="btn primary" onClick={openNew}>
              Add pool
            </button>
          }
        >
          No pools yet. Create one and add target servers to it.
        </Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Strategy</th>
                <th>Members (in order)</th>
                <th>State</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id}>
                  <td className="mono">{p.name}</td>
                  <td>
                    <span className="tag accent">{p.type}</span>
                  </td>
                  <td className="mono muted">
                    {p.members.length
                      ? p.members.map((m) => m.name).join(" → ")
                      : "—"}
                  </td>
                  <td>
                    <StatusDot on={p.enabled} />
                    {p.enabled ? "enabled" : "disabled"}
                  </td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="btn sm ghost" onClick={() => openEdit(p)}>
                      Edit
                    </button>
                    <button className="btn danger" onClick={() => remove(p)}>
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
          title={editing.id ? `Edit ${editing.name}` : "Add pool"}
          onClose={() => setEditing(null)}
        >
          <div className="grid-2">
            <Field label="Name">
              <input value={form.name} onChange={set("name")} />
            </Field>
            <Field label="Strategy">
              <select value={form.type} onChange={set("type")}>
                {POOL_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <Field
            label="Members"
            hint="Order sets fail-over priority. Reorder with the arrows."
          >
            <div className="pool-members">
              {form.member_ids.length === 0 && (
                <div className="muted" style={{ fontSize: 13 }}>
                  No members yet.
                </div>
              )}
              {form.member_ids.map((id, idx) => (
                <div className="member-row" key={idx}>
                  <span className="idx">{idx + 1}</span>
                  <select
                    value={id}
                    onChange={(e) => setMember(idx, e.target.value)}
                  >
                    {servers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.ipaddr}:{s.port})
                      </option>
                    ))}
                  </select>
                  <button
                    className="move"
                    title="Move up"
                    onClick={() => moveMember(idx, -1)}
                  >
                    ↑
                  </button>
                  <button
                    className="move"
                    title="Move down"
                    onClick={() => moveMember(idx, 1)}
                  >
                    ↓
                  </button>
                  <button
                    className="btn danger"
                    onClick={() => removeMember(idx)}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
            <button
              className="btn sm ghost"
              style={{ marginTop: 8 }}
              onClick={addMember}
              disabled={form.member_ids.length >= servers.length}
            >
              + Add member
            </button>
          </Field>

          <div className="check">
            <input
              id="pool-enabled"
              type="checkbox"
              checked={form.enabled}
              onChange={set("enabled")}
            />
            <label htmlFor="pool-enabled" style={{ margin: 0 }}>
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
    </>
  );
}
