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
    syncStatus: () => request("/ldap/sync"),
    syncNow: () => request("/ldap/sync", { method: "POST" }),
  },
  config: {
    preview: () => request("/config/preview"),
    apply: () => request("/config/apply", { method: "POST" }),
    audit: () => request("/config/audit"),
  },
  decisions: {
    list: (params = "") => request(`/decisions${params}`),
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
