import { useSearchParams } from "react-router-dom";
export function originLink(params: URLSearchParams, source: string) {
  const place = params.get("origin_place"),
    tab = params.get("origin_tab"),
    view = params.get("origin_view"),
    id = params.get("origin_item"),
    name = params.get("origin_name");
  if (
    place === "Today" &&
    ["Plan", "Shopping list", "Sell", "Queue", "Extras"].includes(tab ?? "") &&
    ["Today plan", "This session"].includes(view ?? "")
  )
    return {
      label: `← Back to Today · ${view === "This session" ? view : tab}`,
      url:
        "/app/today?" +
        new URLSearchParams({
          source,
          view:
            view === "This session"
              ? "level-up"
              : tab === "Plan"
                ? "opportunities"
                : "route",
        }),
    };
  if (
    place === "Market" &&
    id &&
    /^\d{1,10}$/.test(id) &&
    Number(id) > 0 &&
    Number(id) < 2 ** 32 &&
    name?.trim()
  )
    return {
      label: `← Back to Market · ${name.slice(0, 200)}`,
      url: "/app/market?" + new URLSearchParams({ source, inspect: id }),
    };
  return null;
}
export function Origin({ source }: { source: string }) {
  const [params] = useSearchParams();
  const origin = originLink(params, source);
  return origin ? <a href={origin.url}>{origin.label}</a> : null;
}
