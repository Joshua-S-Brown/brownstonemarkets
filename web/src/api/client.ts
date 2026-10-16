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

export async function post<T>(
  path: string,
  source: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const url = new URL("/api/" + path, window.location.origin);
  url.searchParams.set("source", source);
  const response = await fetch(url, {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json",
      "X-Brownstone-Token":
        document.querySelector<HTMLMetaElement>('meta[name="brownstone-token"]')
          ?.content || "",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(
      result.detail || "Unable to update Today. Retry or open Data.",
    );
  }
  return response.json();
}
