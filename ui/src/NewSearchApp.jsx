import React, { useEffect, useMemo, useRef, useState } from "react";

// CRA-friendly env (build-time):
// Use REACT_APP_API_BASE to call a different origin in production if needed.
// In dev, we rely on "proxy" in package.json.
const API_BASE = (process.env.REACT_APP_API_BASE || "").replace(/\/$/, "");
const API_SECRET_KEY = process.env.REACT_APP_API_SECRET_KEY || "changeme";

function buildUrl(base, path, params) {
  const u = new URL((base || "") + path, window.location.origin);
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    u.searchParams.set(k, String(v));
  });
  return u.toString();
}

function useDebounced(value, ms = 500) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export default function NewsSearchApp() {
  const [query, setQuery] = useState("apple");
  const [city, setCity] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [offline, setOffline] = useState(false);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const debouncedQuery = useDebounced(query, 500);
  const controllerRef = useRef(null);

  const totalPages = data?.total_estimated_pages || 0;
  const canPrev = page > 1;
  const canNext = totalPages ? page < totalPages : true;

  const fetchData = async ({ resetPage = false } = {}) => {
    if (!debouncedQuery.trim()) return;
    if (resetPage) setPage(1);
    const params = {
      query: debouncedQuery.trim(),
      page: resetPage ? 1 : page,
      page_size: pageSize,
      city: city.trim(),
      offline: offline ? 1 : 0
    };
    const url = buildUrl(API_BASE, "/search", params);

    if (controllerRef.current) controllerRef.current.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setLoading(true);
    setError("");

    try {
      const t0 = performance.now();
      const res = await fetch(url, {
        signal: controller.signal,
        headers: {
          "Authorization": `Bearer ${API_SECRET_KEY}`
        }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const t1 = performance.now();
      if (json.time_taken_ms == null) json.time_taken_ms = Math.round(t1 - t0);
      setData(json);
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQuery, page, pageSize, offline]);

  const onSubmit = (e) => {
    e.preventDefault();
    fetchData({ resetPage: true });
  };

  const items = data?.items || [];

  return (
    <div style={{ minHeight: "100vh" }}>
      <header style={{ position: "sticky", top: 0, background: "#fff", borderBottom: "1px solid #eee", zIndex: 1 }}>
        <div style={{ maxWidth: 1000, margin: "0 auto", padding: "12px 16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h1 style={{ fontSize: 20, margin: 0 }}>News Search</h1>
          <small style={{ color: "#666" }}>Guardian + NYT</small>
        </div>
      </header>

      <main style={{ maxWidth: 1000, margin: "0 auto", padding: "16px" }}>
        <form onSubmit={onSubmit} style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 0.7fr 0.5fr auto auto", background: "#fff", border: "1px solid #eaeaea", borderRadius: 14, padding: 12, alignItems: "end" }}>
          <div>
            <label style={{ fontSize: 12, color: "#333" }}>Keyword</label>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. apple, cricket, bitcoin"
              style={{ width: "100%", padding: "8px 10px", borderRadius: 10, border: "1px solid #ddd" }}
            />
          </div>
          <div>
            <label style={{ fontSize: 12, color: "#333" }}>City (optional)</label>
            <input
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="e.g. Bengaluru"
              style={{ width: "100%", padding: "8px 10px", borderRadius: 10, border: "1px solid #ddd" }}
            />
          </div>
          <div>
            <label style={{ fontSize: 12, color: "#333" }}>Page Size</label>
            <select
              value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}
              style={{ width: "100%", padding: "8px 10px", borderRadius: 10, border: "1px solid #ddd", background: "#fff" }}
            >
              {[5,10,20,30,50].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={offline} onChange={(e) => setOffline(e.target.checked)} />
            <span style={{ fontSize: 13 }}>Offline</span>
          </label>
          <button type="submit" disabled={!query.trim() || loading} style={{ padding: "8px 14px", borderRadius: 10, background: "#4f46e5", color: "#fff", border: 0 }}>
            {loading ? "Searching…" : "Search"}
          </button>
        </form>

        <div style={{ marginTop: 12, display: "flex", gap: 12, flexWrap: "wrap", color: "#555", fontSize: 13 }}>
          <span>Page: <b>{data?.page || 1}</b>{totalPages ? ` / ${totalPages}` : ""}</span>
          {typeof data?.time_taken_ms === "number" && <span style={{ background: "#eee", padding: "2px 8px", borderRadius: 999 }}>{data.time_taken_ms} ms</span>}
          {data?.keyword && <span style={{ background: "#eee", padding: "2px 8px", borderRadius: 999 }}>keyword: “{data.keyword}”</span>}
          {data?.city && <span style={{ background: "#eee", padding: "2px 8px", borderRadius: 999 }}>city: {data.city}</span>}
        </div>

        {error && (
          <div style={{ marginTop: 12, border: "1px solid #f4c7c7", background: "#fff4f4", color: "#b00020", padding: 12, borderRadius: 12 }}>
            <b>Error:</b> {error}
          </div>
        )}

        <section style={{ marginTop: 12, display: "grid", gap: 10 }}>
          {items.length === 0 && !loading && (
            <div style={{ background: "#fff", border: "1px solid #eee", borderRadius: 12, padding: 16, color: "#666" }}>
              No articles yet. Try a different keyword.
            </div>
          )}
          {items.map((it, i) => (
            <article key={i} style={{ background: "#fff", border: "1px solid #eee", borderRadius: 12, padding: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <h3 style={{ margin: 0, fontSize: 18 }}>{it.title || "(untitled)"}</h3>
                <span style={{ fontSize: 11, border: "1px solid #eee", padding: "2px 6px", borderRadius: 999 }}>{it.website || it.source}</span>
              </div>
              {it.description && <p style={{ marginTop: 6, color: "#333", fontSize: 14 }}>{it.description}</p>}
              <div style={{ marginTop: 8, display: "flex", gap: 12, flexWrap: "wrap", fontSize: 13, color: "#666" }}>
                {it.published_at && <span>{new Date(it.published_at).toLocaleString()}</span>}
                {it.url && <a href={it.url} target="_blank" rel="noreferrer">Read article ↗</a>}
              </div>
            </article>
          ))}
        </section>

        <div style={{ marginTop: 18, display: "flex", justifyContent: "space-between" }}>
          <button onClick={() => canPrev && setPage(p => Math.max(1, p - 1))} disabled={!canPrev || loading} style={{ padding: "8px 14px", borderRadius: 10, background: "#fff", border: "1px solid #ddd" }}>
            ← Prev
          </button>
          <div style={{ fontSize: 13, color: "#666" }}>Showing {items.length} item(s)</div>
          <button onClick={() => canNext && setPage(p => p + 1)} disabled={!canNext || loading} style={{ padding: "8px 14px", borderRadius: 10, background: "#fff", border: "1px solid #ddd" }}>
            Next →
          </button>
        </div>

        <details style={{ marginTop: 18, background: "#fff", border: "1px solid #eee", borderRadius: 12, padding: 12 }}>
          <summary>Raw response</summary>
          <pre style={{ marginTop: 8, fontSize: 12, overflow: "auto" }}>{JSON.stringify(data, null, 2)}</pre>
        </details>
      </main>
    </div>
  );
}
