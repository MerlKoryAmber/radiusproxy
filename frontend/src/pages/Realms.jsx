import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Modal, Field, Spinner, Empty, StatusDot } from "../components.jsx";

const BLANK = {
  name: "",
  auth_pool_id: null,
  acct_pool_id: null,
  nostrip: false,
  ad_group_check: false,
  required_ad_group: "",
  username_normalization: "none",
  ad_fail_mode: "open",
  enabled: true,
  note: "",
};

export default function Realms({ notify, onChange }) {
  const [rows, setRows] = useState(null);
  const [pools, setPools] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(BLANK);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const [realms, p] = await Promise.all([
      api.realms.list(),
      api.pools.list(),
    ]);
    setRows(realms);
    setPools(p);
  };
  useEffect(() => {
    load();
  }, []);

  const openNew = () => {
    setForm(BLANK);
    setEditing({});
  };
  const openEdit = (r) => {
    setForm({
      name: r.name,
      auth_pool_id: r.auth_pool_id,
      acct_pool_id: r.acct_pool_id,
      nostrip: r.nostrip,
      ad_group_check: r.ad_group_check,
      required_ad_group: r.required_ad_group || "",
      username_normalization: r.username_normalization || "none",
      ad_fail_mode: r.ad_fail_mode || "open",
      enabled: r.enabled,
      note: r.note || "",
    });
    setEditing(r);
  };

  const set = (k) => (e) => {
    const v = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [k]: v }));
  };
  const setPool = (k) => (e) => {
    const v = e.target.value === "" ? null : Number(e.target.value);
    setForm((f) => ({ ...f, [k]: v }));
  };

  const save = async () => {
    setSaving(true);
    try {
      if (editing.id) {
        await api.realms.update(editing.id, form);
        notify(`Realm ${form.name} updated`);
      } else {
        await api.realms.create(form);
        notify(`Realm ${form.name} created`);
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
    if (!confirm(`Delete realm "${r.name}"?`)) return;
    try {
      await api.realms.remove(r.id);
      notify(`Realm ${r.name} deleted`);
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
          <h1>Realms</h1>
          <p>
            The routing table. A realm matches the suffix after{" "}
            <span className="mono">@</span> in the User-Name and points requests
            at a pool.
          </p>
        </div>
        <button className="btn primary" onClick={openNew}>
          Add realm
        </button>
      </div>

      {rows.length === 0 ? (
        <Empty
          action={
            <button className="btn primary" onClick={openNew}>
              Add realm
            </button>
          }
        >
          No realms yet. Add realms to route proxied requests to your pools.
        </Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Realm</th>
                <th>Auth pool</th>
                <th>Acct pool</th>
                <th>Strip suffix</th>
                <th>AD gate</th>
                <th>State</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="mono">{r.name}</td>
                  <td className="mono muted">{r.auth_pool_name || "—"}</td>
                  <td className="mono muted">{r.acct_pool_name || "—"}</td>
                  <td>
                    {r.nostrip ? (
                      <span className="tag off">keep</span>
                    ) : (
                      <span className="tag">strip</span>
                    )}
                  </td>
                  <td>
                    {r.ad_group_check ? (
                      <span className="tag accent" title={r.required_ad_group}>
                        {r.ad_fail_mode === "closed" ? "closed" : "open"}
                      </span>
                    ) : (
                      <span className="tag off">off</span>
                    )}
                  </td>
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
          title={editing.id ? `Edit ${editing.name}` : "Add realm"}
          onClose={() => setEditing(null)}
        >
          <Field
            label="Realm name"
            hint="e.g. example.com, or DEFAULT to catch everything else"
          >
            <input value={form.name} onChange={set("name")} />
          </Field>
          <div className="grid-2">
            <Field label="Auth pool">
              <select value={form.auth_pool_id ?? ""} onChange={setPool("auth_pool_id")}>
                <option value="">— none —</option>
                {pools.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Acct pool" hint="same as auth → renders as pool =">
              <select value={form.acct_pool_id ?? ""} onChange={setPool("acct_pool_id")}>
                <option value="">— none —</option>
                {pools.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div className="check">
            <input
              id="nostrip"
              type="checkbox"
              checked={form.nostrip}
              onChange={set("nostrip")}
            />
            <label htmlFor="nostrip" style={{ margin: 0 }}>
              Keep realm suffix on User-Name (nostrip)
            </label>
          </div>
          <div className="check" style={{ marginTop: 10 }}>
            <input
              id="ad-check"
              type="checkbox"
              checked={form.ad_group_check}
              onChange={set("ad_group_check")}
            />
            <label htmlFor="ad-check" style={{ margin: 0 }}>
              Check AD group membership before proxying
            </label>
          </div>
          {form.ad_group_check && (
            <>
              <Field
                label="Required AD group"
                hint="DN of the group the user must belong to, e.g. CN=vpn-users,OU=Groups,DC=corp,DC=example,DC=com"
              >
                <input
                  value={form.required_ad_group}
                  onChange={set("required_ad_group")}
                  placeholder="CN=vpn-users,OU=Groups,DC=corp,DC=example,DC=com"
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
                <Field
                  label="If AD is unreachable"
                  hint="open = proxy anyway (default); closed = reject"
                >
                  <select
                    value={form.ad_fail_mode}
                    onChange={set("ad_fail_mode")}
                  >
                    <option value="open">fail-open</option>
                    <option value="closed">fail-closed</option>
                  </select>
                </Field>
              </div>
            </>
          )}
          <div className="check" style={{ marginTop: 10 }}>
            <input
              id="realm-enabled"
              type="checkbox"
              checked={form.enabled}
              onChange={set("enabled")}
            />
            <label htmlFor="realm-enabled" style={{ margin: 0 }}>
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
