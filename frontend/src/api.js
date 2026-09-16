import { useCallback, useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";
export const TOKEN_KEY = "globetrotter_token";
export const MAX_FILE_BYTES = 5_000_000;
export const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
export const MEDIA_TYPES = [...IMAGE_TYPES, "video/mp4", "video/webm"];

export function validateFile(file, imageOnly = false) {
  if (!file || file.size === 0) return "Choose a non-empty file.";
  if (file.size >= MAX_FILE_BYTES) return "Each file must be strictly less than 5 MB (5,000,000 bytes).";
  if (!(imageOnly ? IMAGE_TYPES : MEDIA_TYPES).includes(file.type)) {
    return imageOnly ? "Choose a JPEG, PNG, WebP, or GIF image." : "Choose a JPEG, PNG, WebP, GIF, MP4, or WebM file.";
  }
  return "";
}

export async function request(path, { body, responseType = "json", ...options } = {}) {
  const token = localStorage.getItem(TOKEN_KEY);
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: options.signal
        ? AbortSignal.any([options.signal, AbortSignal.timeout(20000)])
        : AbortSignal.timeout(20000),
      headers: {
        ...(body && !(body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? (body instanceof FormData ? body : JSON.stringify(body)) : undefined,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Cannot reach GlobeTrotter. Check your connection and try again.");
  }
  if (response.status === 401 && !["/auth/login", "/auth/signup"].includes(path)) {
    window.dispatchEvent(new Event("session-expired"));
  }
  if (response.status === 204) return null;
  if (response.ok && responseType === "blob") return response.blob();
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
