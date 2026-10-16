import styles from "../theme/app.module.css";
import { lazy, Suspense, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import * as Popover from "@radix-ui/react-popover";
import { get, type Sources } from "../api/client";
import { Market } from "../places/market/Market";
import { Inspector } from "./Inspector";
import { Palette, places, placeURL } from "./Palette";
import { EmptyState, ErrorState, Pill, Tip } from "../ui/parts";
const Today = lazy(() =>
  import("../places/today/Today").then((m) => ({ default: m.Today })),
);
const Team = lazy(() =>
  import("../places/team/Team").then((m) => ({ default: m.Team })),
);
function Theme() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem("brownstone-theme") || "system",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("brownstone-theme", theme);
  }, [theme]);
  return (
    <select
      aria-label="Theme"
      value={theme}
      onChange={(e) => setTheme(e.target.value)}
    >
      <option value="system">System</option>
      <option value="light">Light</option>
      <option value="dark">Dark</option>
    </select>
  );
}
export function App() {
  const [params, setParams] = useSearchParams();
  const requested = params.get("source") || "";
  const query = useQuery({
    queryKey: [requested, "sources"],
    queryFn: ({ signal }) =>
      get<Sources>("sources?inventory=false", requested, signal),
  });
  const data = query.data,
    source = data?.selected?.source_id || "";
  const inventory = useQuery({
    queryKey: [source, "inventory"],
    queryFn: ({ signal }) => get<Sources>("sources", source, signal),
    enabled: !!source,
  });
  const waiting = inventory.data?.waiting,
    waitingError = inventory.data?.waiting_error;
  useEffect(() => {
    if (!source) return;
    let socket: WebSocket | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;
    const connect = () => {
      const url = new URL("/api/presence", window.location.origin);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      url.searchParams.set("source", source);
      socket = new WebSocket(url);
      socket.onclose = () => {
        if (!stopped) retry = setTimeout(connect, 5000);
      };
    };
    connect();
    return () => {
      stopped = true;
      clearTimeout(retry);
      socket?.close();
    };
  }, [source]);
  function choose(id: string) {
    const next = new URLSearchParams(params);
    next.set("source", id);
    next.delete("inspect");
    next.delete("variant");
    setParams(next);
  }
  return (
    <Inspector key={source} source={source}>
      <div className={styles["shell"]}>
        <nav className={styles["rail"]} aria-label="Places">
          <div className={styles["brand"]}>
            <span className={styles["brand-mark"]}>B</span>
            <span>
              Brownstone<small>MARKETS WORKSPACE</small>
            </span>
          </div>
          {places.map((p) => (
            <a key={p} className={styles["nav-btn"]} href={placeURL(p, source)}>
              <span>
                {p}
                <small>{data?.questions[p]}</small>
              </span>
            </a>
          ))}
          <Dialog.Root>
            <Dialog.Trigger className={styles["data-button"]}>
              Data <Pill>{waiting ?? "?"}</Pill>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className={styles["shade"]} />
              <Dialog.Content
                className={styles["inspector"]}
                aria-describedby={undefined}
              >
                <Dialog.Title>Data</Dialog.Title>
                <Dialog.Close>Close ✕</Dialog.Close>
                <p>
                  {inventory.isFetching
                    ? "Checking local and dropped scan files…"
                    : `${waiting ?? "Unknown"} new scans waiting`}
                </p>
                {waitingError && <p role="alert">{waitingError}</p>}
                <a href={placeURL("Data", source)}>Review scans in Data →</a>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        </nav>
        <div className={styles["main"]}>
          <header className={styles["topbar"]}>
            <Palette source={source} />
            <Popover.Root>
              <Popover.Trigger className={styles["chip"]}>
                {data?.selected?.label || "Choose source"} ▾
              </Popover.Trigger>
              <Popover.Portal>
                <Popover.Content className={styles["popover"]} sideOffset={8}>
                  <h2>Choose a source</h2>
                  {data?.sources.map((s) => (
                    <Popover.Close asChild key={s.source_id}>
                      <button
                        className={styles["source-option"]}
                        onClick={() => choose(s.source_id)}
                      >
                        {s.game_version} · {s.label}
                      </button>
                    </Popover.Close>
                  ))}
                  <p>Each source is separate.</p>
                </Popover.Content>
              </Popover.Portal>
            </Popover.Root>
            <Tip
              text={
                data?.evidence
                  ? `${data.evidence.source_id} · ${data.evidence.market_id} · ${data.evidence.finished_at ?? "No scan"}`
                  : "Select one source. Open Data to import saved scans."
              }
            >
              <Pill
                tone={
                  data?.evidence?.freshness?.stale
                    ? "warn"
                    : data?.evidence?.freshness?.upstream_known
                      ? "good"
                      : "neutral"
                }
              >
                {!data?.evidence?.freshness
                  ? "No scan"
                  : !data.evidence.freshness.upstream_known
                    ? "Price age unknown"
                    : data.evidence.freshness.stale
                      ? "Stale"
                      : "Fresh"}
              </Pill>
            </Tip>
            <Theme />
          </header>
          <main className={styles["workspace"]}>
            {!["/app/market", "/app/today", "/app/team"].includes(
              window.location.pathname,
            ) && <p className={styles["eyebrow"]}>Your saved market</p>}
            {!["/app/market", "/app/today", "/app/team"].includes(
              window.location.pathname,
            ) && <h1>Brownstone workspace</h1>}
            {!["/app/market", "/app/today", "/app/team"].includes(
              window.location.pathname,
            ) && (
              <p className={styles["muted"]}>
                What should I do today to make gold?
              </p>
            )}
            {query.error ? (
              <ErrorState
                source={source}
                error={query.error}
                retry={() => {
                  void query.refetch();
                }}
              />
            ) : !data ? (
              <p role="status">Loading sources…</p>
            ) : !source ? (
              <EmptyState title="Choose a source">
                {data.sources.length
                  ? "Several sources are enabled. Choose one above to browse its saved evidence."
                  : "No sources are enabled. Enable a source in your local configuration, then reload."}
              </EmptyState>
            ) : window.location.pathname === "/app/today" ? (
              <Suspense fallback={<p role="status">Loading Today…</p>}>
                <Today key={source} source={source} waiting={waiting} />
              </Suspense>
            ) : window.location.pathname === "/app/team" ? (
              <Suspense fallback={<p role="status">Loading Team…</p>}>
                <Team key={source} source={source} />
              </Suspense>
            ) : window.location.pathname === "/app/market" ? (
              <Market source={source} />
            ) : (
              <EmptyState title="Find an item. Follow the evidence.">
                Search for an item or character with ⌘K. Each place opens its
                existing page while the workspace takes shape.
                <p>
                  <a
                    className={styles["primary"]}
                    href={placeURL("Today", source)}
                  >
                    Open Today →
                  </a>
                </p>
              </EmptyState>
            )}
            <div className={styles["foundation-note"]}>
              <Pill>Local evidence</Pill>
              <span>Saved scans · read only</span>
            </div>
          </main>
        </div>
      </div>
    </Inspector>
  );
}
