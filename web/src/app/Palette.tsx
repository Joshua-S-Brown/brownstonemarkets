import styles from "../theme/app.module.css";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import * as Dialog from "@radix-ui/react-dialog";
import { get, type SearchHit } from "../api/client";
import { useInspector } from "./InspectorContext";
import { ErrorState } from "../ui/parts";
export const places = [
  "Today",
  "Market",
  "Supply chains",
  "Team",
  "Ledger",
] as const;
export function placeURL(place: string, source: string) {
  if (place === "Today") return "/app/today?" + new URLSearchParams({ source });
  if (place === "Team") return "/app/team?" + new URLSearchParams({ source });
  if (place === "Market")
    return "/app/market?" + new URLSearchParams({ source });
  return (
    "/?" +
    new URLSearchParams({
      place:
        place === "Ledger"
          ? "Stock"
          : place === "Supply chains"
            ? "Market"
            : place,
      source,
    })
  );
}
export function Palette({ source }: { source: string }) {
  const [open, setOpen] = useState(false),
    [q, setQ] = useState("");
  const inspect = useInspector();
  const [search, setSearch] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setSearch(q), 200);
    return () => clearTimeout(timer);
  }, [q]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);
  const query = useQuery({
    queryKey: [source, "search", search],
    queryFn: ({ signal }) =>
      get<SearchHit[]>(
        "search?q=" + encodeURIComponent(search),
        source,
        signal,
      ),
    enabled: open && !!source && !!search.trim(),
  });
  return (
    <>
      <button className={styles["search-btn"]} onClick={() => setOpen(true)}>
        Search items, characters, places <kbd>⌘K</kbd>
      </button>
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className={styles["palette-shade"]} />
          <Dialog.Content
            className={styles["palette"]}
            aria-describedby={undefined}
          >
            <Dialog.Title className={styles["sr-only"]}>
              Search saved records and places
            </Dialog.Title>
            <Command label="Search" shouldFilter={false}>
              <Command.Input
                value={q}
                onValueChange={setQ}
                placeholder="Search by name or item ID…"
              />
              <Command.List>
                <Command.Empty>
                  {query.isFetching
                    ? "Searching saved evidence…"
                    : !source
                      ? "Choose a source to search items and characters."
                      : "No matches. Try a name or item ID."}
                </Command.Empty>
                <Command.Group heading="Places">
                  {places
                    .filter((p) => p.toLowerCase().includes(q.toLowerCase()))
                    .map((p) => (
                      <Command.Item
                        key={p}
                        value={p}
                        onSelect={() => {
                          window.location.href = placeURL(p, source);
                        }}
                      >
                        {p}
                      </Command.Item>
                    ))}
                </Command.Group>
                {query.error && (
                  <ErrorState
                    source={source}
                    error={query.error}
                    retry={() => {
                      void query.refetch();
                    }}
                  />
                )}
                <Command.Group heading="Saved records">
                  {query.data?.map((hit, i) => (
                    <Command.Item
                      key={i}
                      value={hit.kind + hit.name + i}
                      onSelect={() => {
                        inspect(
                          hit.item_id
                            ? {
                                item: hit.item_id,
                                variant: JSON.stringify([
                                  hit.variant_state,
                                  hit.variant_id,
                                ]),
                              }
                            : { character: hit.character! },
                        );
                        setOpen(false);
                      }}
                    >
                      {hit.name}
                      <small>
                        {hit.kind === "item"
                          ? `${hit.item_id} · ${hit.variant_state || "legacy"}${hit.variant_id ? " · " + hit.variant_id : ""}`
                          : "Team"}
                      </small>
                    </Command.Item>
                  ))}
                </Command.Group>
              </Command.List>
            </Command>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
