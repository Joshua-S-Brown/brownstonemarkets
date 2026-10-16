import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "../../api/client";
import { ItemLink } from "../../ui/ItemLink";
import { Evidence } from "../../ui/Evidence";
import { Money } from "./Money";
import { ErrorState } from "../../ui/parts";
import { Cost, Steps } from "./Path";
import type { Estimate, HireDetailData, HireRow } from "./types";
type Tier = {
  cap: number;
  required_level: number | null;
  source?: string;
  tier_fees: string;
  estimate: Estimate;
  best: HireRow["best"];
  feeds: {
    count: number;
    top: { material: string; recipe: string; saved_copper: number }[];
  };
};
export const title = (name: string) =>
  name
    .split("-")
    .map((s) => s[0].toUpperCase() + s.slice(1))
    .join(" ");
export function HireDetail({ data }: { data: HireDetailData }) {
  return (
    <>
      <p>
        New hire: rank 1, no known recipes · {data.needs_pattern} needs pattern
        or other source · {data.unknown_source} learning source unknown
      </p>
      {(data.tiers as Tier[]).map((t) => (
        <section key={t.cap}>
          <h3>
            Rank {t.cap}
            {t.required_level != null &&
              ` · character level ${t.required_level}${t.source === "classic_fallback" ? " (Classic level, unconfirmed on Forever)" : ""}`}
          </h3>
          <p>
            Cumulative cost from rank 1: <Cost estimate={t.estimate} />
          </p>
          <p>{t.tier_fees}</p>
          <p>
            Best trainer recipe:{" "}
            {t.best ? (
              <>
                <ItemLink
                  id={t.best.output_item_id}
                  name={t.best.output_name}
                />{" "}
                · <Money copper={t.best.profit_copper} /> per craft
              </>
            ) : (
              "no valued board recipe"
            )}
          </p>
          <p>
            What it feeds:{" "}
            {t.feeds.count
              ? `${t.feeds.count} current team board rows become cheaper`
              : "feeds nothing"}
          </p>
          {t.feeds.top.map((s, i) => (
            <p key={i}>
              {s.material} → {s.recipe} · <Money copper={s.saved_copper} />{" "}
              saved per craft
            </p>
          ))}
          <Steps estimate={t.estimate} />
          <details>
            <summary>Tier evidence and assumptions</summary>
            <Evidence data={t} />
          </details>
        </section>
      ))}
    </>
  );
}
export function Hire({
  row,
  source,
  showCost,
}: {
  row: HireRow;
  source: string;
  showCost: boolean;
}) {
  const [open, setOpen] = useState(false);
  const query = useQuery({
    queryKey: [source, "team-hire", row.profession],
    queryFn: ({ signal }) =>
      get<HireDetailData>(
        "team/hire/" + encodeURIComponent(row.profession),
        source,
        signal,
      ),
    enabled: open,
    staleTime: Infinity,
  });
  return (
    <details onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>
        {title(row.profession)} · best at 300:{" "}
        <Money copper={row.best?.profit_copper ?? null} /> per craft
        {showCost && (
          <>
            {" "}
            · cost to 300:{" "}
            {row.estimate.complete ? (
              <Money copper={row.estimate.cost_copper ?? null} />
            ) : (
              "incomplete"
            )}
          </>
        )}
        <small>
          Team:{" "}
          {row.holders.length
            ? row.holders
                .map(
                  (h) =>
                    `${h.character.join(" · ")} · ${h.rank ?? "unknown"} / ${h.max_rank ?? "unknown"}`,
                )
                .join("; ")
            : "no evidenced holder"}
        </small>
      </summary>
      {open &&
        (query.error ? (
          <ErrorState
            source={source}
            error={query.error}
            retry={() => {
              void query.refetch();
            }}
          />
        ) : query.data ? (
          <HireDetail data={query.data} />
        ) : (
          <p role="status">Loading tier detail…</p>
        ))}
    </details>
  );
}
