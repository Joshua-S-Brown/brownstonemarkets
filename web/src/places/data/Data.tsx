import { lazy, Suspense, useEffect, useRef, useState } from "react";
import styles from "../../theme/app.module.css";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post } from "../../api/client";
import type { components } from "../../api/schema";
import { Evidence } from "../../ui/Evidence";
import { ErrorState, Pill } from "../../ui/parts";
import type { Reviewed } from "./Review";
const Review = lazy(() =>
  import("./Review").then((m) => ({ default: m.Review })),
);
function Imported({ source }: { source: string }) {
  const query = useQuery({
    queryKey: [source, "data", "imported"],
    queryFn: ({ signal }) => get<object[]>("data/imported", source, signal),
  });
  return (
    <>
      {query.error && <p role="alert">{query.error.message}</p>}
      {query.data && <Evidence data={{ imported: query.data }} />}
    </>
  );
}
export function Data({ source }: { source: string }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: [source, "data"],
    queryFn: ({ signal }) =>
      get<components["schemas"]["Data"]>("data", source, signal),
  });
  const [review, setReview] = useState<Reviewed | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [imported, setImported] = useState(false);
  const active = useRef(true),
    id = useRef<string | null>(null);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      void post("data/discard", source, { review_id: id.current }).catch(
        () => {},
      );
    };
  }, [source]);
  async function check() {
    setBusy(true);
    setError("");
    setReview(null);
    try {
      const result = await post<Reviewed>("data/review", source, {});
      if (active.current) {
        id.current = result.review_id ?? null;
        setReview(result);
      } else {
        void post("data/discard", source, {
          review_id: result.review_id,
        }).catch(() => {});
      }
    } catch (e) {
      if (active.current) setError((e as Error).message);
    } finally {
      if (active.current) setBusy(false);
    }
  }
  async function collect(selected: string[]) {
    setBusy(true);
    setError("");
    try {
      const result = await post<Reviewed>("data/import", source, {
        review_id: review?.review_id,
        selected,
      });
      if (result.success)
        await client.invalidateQueries({
          predicate: (q) => q.queryKey[0] === source,
        });
      if (active.current) {
        id.current = result.review_id ?? null;
        setReview(result);
      }
    } catch (e) {
      if (active.current) {
        setError((e as Error).message);
        setReview(null);
        id.current = null;
      }
    } finally {
      if (active.current) setBusy(false);
    }
  }
  return (
    <>
      {query.error && (
        <ErrorState
          source={source}
          error={query.error}
          retry={() => void query.refetch()}
        />
      )}
      {query.data && (
        <>
          {query.data.provider !== "addon" ? (
            <p>{query.data.cli}</p>
          ) : (
            <>
              <div>
                {query.data.chips.map((c, i) => (
                  <Pill key={i}>{c}</Pill>
                ))}
              </div>
              <details>
                <summary>ⓘ Import details</summary>
                <Evidence data={query.data.details} />
                <p>
                  Partial scans are preserved but never feed prices. Reads use
                  best-effort change detection. If the drop folder is still
                  syncing, check again in a minute.
                </p>
              </details>
              <h2>Bring in new scans</h2>
              <p>
                Reads this Mac’s game file and the drop folder. Nothing is saved
                until you choose Import.
              </p>
              <button
                className={
                  !review?.review?.can_import ? styles["primary"] : undefined
                }
                disabled={busy}
                onClick={() => void check()}
              >
                Check for new scans
              </button>
              {busy && <p role="status">Working…</p>}
              {error && <p role="alert">{error}</p>}
              {review?.messages.map(([kind, message], i) => (
                <p key={i} role={kind === "error" ? "alert" : "status"}>
                  {message}
                </p>
              ))}
              {review?.review && (
                <Suspense fallback={<p>Loading review…</p>}>
                  <Review
                    source={source}
                    key={review.review_id}
                    data={review}
                    busy={busy}
                    collect={(selected) => void collect(selected)}
                  />
                </Suspense>
              )}
              {!!review?.hits.length && (
                <details open>
                  <summary>Watchlist hits ({review.hits.length})</summary>
                  {review.hits.map((h, i) => (
                    <p key={i}>{h}</p>
                  ))}
                </details>
              )}
              <details onToggle={(e) => setImported(e.currentTarget.open)}>
                <summary>What&apos;s imported</summary>
                {imported && <Imported source={source} />}
              </details>
            </>
          )}
        </>
      )}
    </>
  );
}
