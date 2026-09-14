import { useCallback, useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";
export const TOKEN_KEY = "globetrotter_token";

export async function request(path, { body, ...options } = {}) {
  const token = localStorage.getItem(TOKEN_KEY);
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: options.signal
        ? AbortSignal.any([options.signal, AbortSignal.timeout(20000)])
        : AbortSignal.timeout(20000),
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Cannot reach GlobeTrotter. Check your connection and try again.");
  }
  if (response.status === 401 && !["/auth/login", "/auth/signup"].includes(path)) {
    window.dispatchEvent(new Event("session-expired"));
  }
  if (response.status === 204) return null;
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new Error("The server returned an unexpected response. Please try again.");
  }
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => `${item.loc?.slice(1).join(" ") || "Input"}: ${item.msg}`).join(". ")
      : data.detail;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return data;
}

export function useData(path) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((current) => current + 1), []);
  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError("");
    request(path, { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) setData(value); })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [path, version]);
  return { data, setData, error, loading, reload };
}
