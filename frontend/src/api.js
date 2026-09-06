// Thin fetch wrapper. Every call goes through /api, proxied to FastAPI.
async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
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
  homeServers: {
    list: () => request("/home-servers"),
    create: (body) =>
      request("/home-servers", { method: "POST", body: JSON.stringify(body) }),
    update: (id, body) =>
      request(`/home-servers/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    remove: (id) => request(`/home-servers/${id}`, { method: "DELETE" }),
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
  realms: {
    list: () => request("/realms"),
    create: (body) =>
      request("/realms", { method: "POST", body: JSON.stringify(body) }),
    update: (id, body) =>
      request(`/realms/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    remove: (id) => request(`/realms/${id}`, { method: "DELETE" }),
  },
  ldap: {
    get: () => request("/ldap"),
    update: (body) =>
      request("/ldap", { method: "PUT", body: JSON.stringify(body) }),
    previewUrl: "/api/ldap/preview.conf",
  },
  config: {
    preview: () => request("/config/preview"),
    apply: () => request("/config/apply", { method: "POST" }),
    audit: () => request("/config/audit"),
  },
};
