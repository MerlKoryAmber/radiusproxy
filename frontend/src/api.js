// Thin fetch wrapper. Every call goes through /api, proxied to FastAPI.
export function getToken() {
  try {
    return localStorage.getItem("radpanel_token") || "";
  } catch {
    return "";
  }
}
export function setToken(t) {
  try {
    if (t) localStorage.setItem("radpanel_token", t);
    else localStorage.removeItem("radpanel_token");
  } catch {
    /* storage unavailable */
  }
}

async function request(path, options = {}) {
  const token = getToken();
  const res = await fetch(`/api${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  });
  if (res.status === 401) {
    setToken("");
    throw new Error("unauthorized");
  }
  if (res.status === 204) return null;
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data?.detail ?? data ?? res.statusText;
    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail)
    );
  }
  return data;
}

// Fetch a text/plain endpoint (e.g. a generated .conf) with the Bearer token.
async function requestText(path) {
  const token = getToken();
  const res = await fetch(`/api${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (res.status === 401) {
    setToken("");
    throw new Error("unauthorized");
  }
  const text = await res.text();
  if (!res.ok) throw new Error(text || res.statusText);
  return text;
}

export const api = {
  targetServers: {
    list: () => request("/target-servers"),
    create: (body) =>
      request("/target-servers", { method: "POST", body: JSON.stringify(body) }),
    update: (id, body) =>
      request(`/target-servers/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    remove: (id) => request(`/target-servers/${id}`, { method: "DELETE" }),
  },
  clients: {
    list: () => request("/clients"),
    create: (body) =>
      request("/clients", { method: "POST", body: JSON.stringify(body) }),
    update: (id, body) =>
      request(`/clients/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    remove: (id) => request(`/clients/${id}`, { method: "DELETE" }),
  },
  rules: {
    list: () => request("/rules"),
    create: (body) =>
      request("/rules", { method: "POST", body: JSON.stringify(body) }),
    update: (id, body) =>
      request(`/rules/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    remove: (id) => request(`/rules/${id}`, { method: "DELETE" }),
    reorder: (ids) =>
      request("/rules/reorder", { method: "POST", body: JSON.stringify({ ids }) }),
  },
  pools: {
    list: () => request("/pools"),
    create: (body) =>
      request("/pools", { method: "POST", body: JSON.stringify(body) }),
    update: (id, body) =>
      request(`/pools/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    remove: (id) => request(`/pools/${id}`, { method: "DELETE" }),
  },
  ldap: {
    get: () => request("/ldap"),
    update: (body) =>
      request("/ldap", { method: "PUT", body: JSON.stringify(body) }),
    previewUrl: "/api/ldap/preview.conf",
    test: () => request("/ldap/test", { method: "POST" }),
    syncStatus: () => request("/ldap/sync"),
    syncNow: () => request("/ldap/sync", { method: "POST" }),
    groups: (q) => request(`/ldap/groups?q=${encodeURIComponent(q || "")}`),
  },
  config: {
    preview: () => request("/config/preview"),
    // Raw .conf text for each generated file (PlainTextResponse endpoints).
    clientsPreview: () => requestText("/config/clients-preview.conf"),
    policyPreview: () => requestText("/config/policy-preview.conf"),
    apply: () => request("/config/apply", { method: "POST" }),
    audit: () => request("/config/audit"),
    export: () => request("/config/export"),
    import: (bundle, dryRun = true) =>
      request(`/config/import?dry_run=${dryRun}`, {
        method: "POST",
        body: JSON.stringify(bundle),
      }),
  },
  decisions: {
    list: (params = "") => request(`/decisions${params}`),
  },
  logs: {
    radius: (lines = 300, q = "") =>
      request(`/logs/radius?lines=${lines}&q=${encodeURIComponent(q)}`),
  },
  dashboard: {
    get: () => request("/dashboard"),
  },
  system: {
    getAccess: () => request("/system/access"),
    setAccess: (ip_allowlist) =>
      request("/system/access", {
        method: "PUT",
        body: JSON.stringify({ ip_allowlist }),
      }),
    getTls: () => request("/system/tls"),
    replaceTls: (cert_pem, key_pem) =>
      request("/system/tls", {
        method: "PUT",
        body: JSON.stringify({ cert_pem, key_pem }),
      }),
    regenTls: () => request("/system/tls/self-signed", { method: "POST" }),
    host: () => request("/system/host"),
  },
  auth: {
    status: () => request("/auth/status"),
    login: (username, password) =>
      request("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }),
    setEnabled: (enabled) =>
      request("/auth/settings", {
        method: "PUT",
        body: JSON.stringify({ enabled }),
      }),
    changePassword: (username, new_password) =>
      request("/auth/password", {
        method: "PUT",
        body: JSON.stringify({ username, new_password }),
      }),
  },
};
