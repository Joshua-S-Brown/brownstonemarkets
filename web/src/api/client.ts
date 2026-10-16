import type { components } from "./schema";
export type Sources = components["schemas"]["Sources"];
export type Item = components["schemas"]["Item"];
export type SearchHit = components["schemas"]["SearchHit"];
export async function get<T>(
  path: string,
  source: string,
  signal?: AbortSignal,
): Promise<T> {
  const url = new URL("/api/" + path, window.location.origin);
  url.searchParams.set("source", source);
  const response = await fetch(url, { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      body.detail || "Unable to read saved evidence. Retry or open Data.",
    );
  }
  return response.json();
}
