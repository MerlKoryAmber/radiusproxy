import { useRef, useState } from "react";
import { api } from "../api.js";

// Import / export of the panel's routing data (targets/pools/clients/rules)
// as a portable, name-referenced JSON bundle (ADR-0007). Import is dry-run
// first: upload → plan → confirm → apply. Secrets are not exported.
export default function Portable({ notify, onChange }) {
  const [bundle, setBundle] = useState(null); // parsed uploaded file
  const [fileName, setFileName] = useState("");
  const [plan, setPlan] = useState(null); // dry-run result
  const [applied, setApplied] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const reset = () => {
    setBundle(null);
    setFileName("");
    setPlan(null);
    setApplied(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const doExport = async () => {
    setBusy(true);
    try {
      const data = await api.config.export();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const ts = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `radiusproxy-config-${ts}.json`;
      a.click();
      URL.revokeObjectURL(url);
      notify("Configuration exported");
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  const onFile = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setApplied(null);
    setPlan(null);
    try {
      const parsed = JSON.parse(await f.text());
      setBundle(parsed);
      setFileName(f.name);
    } catch {
      notify("Not valid JSON", "err");
      reset();
    }
  };

  const dryRun = async () => {
    if (!bundle) return;
    setBusy(true);
    setApplied(null);
    try {
      const p = await api.config.import(bundle, true);
      setPlan(p);
      if (p.problems.length)
        notify(`${p.problems.length} problem(s) — fix before applying`, "err");
      else notify("Dry-run ok — review the plan, then Apply");
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  const apply = async () => {
    if (!bundle) return;
    setBusy(true);
    try {
      const r = await api.config.import(bundle, false);
      setApplied(r);
      setPlan(null);
      notify(
        `Imported: ${r.counts.create} created, ${r.counts.update} updated`
      );
      onChange?.();
    } catch (e) {
      notify(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  const canApply = plan && !plan.problems.length && plan.items.length > 0;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Import / Export</h1>
          <p>
            Move the routing config (target servers, pools, clients, rules) in
            and out as one JSON file — backup, or migrate from another RADIUS
            setup. Secrets are <b>not</b> exported; on import a shared secret is
            needed only to create a new target/client.
          </p>
        </div>
        <button className="btn ghost" disabled={busy} onClick={doExport}>
          Export current config
        </button>
      </div>

      <fieldset className="settings-section" style={{ marginBottom: 16 }}>
        <legend>Import from file</legend>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            onChange={onFile}
          />
          <button className="btn" disabled={!bundle || busy} onClick={dryRun}>
            Dry-run
          </button>
          <button
            className="btn primary"
            disabled={!canApply || busy}
            onClick={apply}
          >
            Apply import
          </button>
          {(bundle || plan || applied) && (
            <button className="btn sm ghost" disabled={busy} onClick={reset}>
              Clear
            </button>
          )}
          {fileName && <span className="muted mono">{fileName}</span>}
        </div>
        <p className="field-hint" style={{ marginTop: 8 }}>
          Dry-run shows what will be created/updated without writing. Matching is
          by <b>name</b>: existing → update, new → create. After import, go to{" "}
          <b>Config &amp; apply</b> to write it into FreeRADIUS.
        </p>
      </fieldset>

      {applied && (
        <div className="result ok">
          <h3 style={{ color: "var(--ok)" }}>Imported</h3>
          <div className="muted">
            {applied.counts.create} created · {applied.counts.update} updated.
            Now open <b>Config &amp; apply</b> to push it to FreeRADIUS.
          </div>
        </div>
      )}

      {plan && plan.problems.length > 0 && (
        <div className="result err" style={{ marginBottom: 16 }}>
          <h3 style={{ color: "var(--danger)" }}>
            {plan.problems.length} problem(s) — nothing will be written
          </h3>
          <table>
            <thead>
              <tr><th>Kind</th><th>Name</th><th>Problem</th></tr>
            </thead>
            <tbody>
              {plan.problems.map((p, i) => (
                <tr key={i}>
                  <td className="mono">{p.kind}</td>
                  <td>{p.name}</td>
                  <td>{p.error}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {plan && plan.items.length > 0 && (
        <div className="config-pane">
          <header>
            <span className="path">
              Plan — {plan.counts.create} create, {plan.counts.update} update
              {plan.dry_run ? " (dry-run)" : ""}
            </span>
          </header>
          <table>
            <thead>
              <tr><th>Kind</th><th>Name</th><th>Action</th><th>Note</th></tr>
            </thead>
            <tbody>
              {plan.items.map((it, i) => (
                <tr key={i}>
                  <td className="mono">{it.kind}</td>
                  <td>{it.name}</td>
                  <td>
                    <span className={`tag ${it.action === "create" ? "accent" : "off"}`}>
                      {it.action}
                    </span>
                  </td>
                  <td className="muted">{it.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
