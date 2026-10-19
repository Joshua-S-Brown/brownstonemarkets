import { useInspector } from "../../app/InspectorContext";
import { CharacterName } from "../../ui/CharacterName";
import { Panel } from "../../ui/Panel";
import { Pill, Tip } from "../../ui/parts";
import { Money } from "./Money";
import { Hire, title } from "./Hiring";
import type { Estimate, TeamData } from "./types";
import styles from "./team.module.css";
export function EstimatePill({
  estimate,
}: {
  estimate: Estimate | null | undefined;
}) {
  return (
    <Tip
      text={
        estimate?.reasons?.join("; ") ||
        (estimate?.complete
          ? "All steps valued; no sales credit"
          : "No complete reach estimate available")
      }
    >
      <Pill tone={estimate?.complete ? "good" : "warn"}>
        {estimate?.complete ? "Complete" : "Incomplete"}
      </Pill>
    </Tip>
  );
}
export function HiringTables({
  data,
  source,
  window,
}: {
  data: TeamData;
  source: string;
  window: number;
}) {
  const inspect = useInspector();
  return (
    <>
      <Panel
        title="If we add a character"
        subtitle="Rank 1, no recipes · estimates to 300"
      >
        <div className={styles.scroll}>
          <table>
            <thead>
              <tr>
                <th>Profession</th>
                <th>Cost to 300</th>
                <th>Best per craft at 300</th>
                <th>Team holder</th>
                <th>Estimate</th>
              </tr>
            </thead>
            <tbody>
              {data.hires.map((r) => (
                <tr key={r.profession}>
                  <td>
                    <button
                      onClick={() => inspect({ profession: r.profession })}
                    >
                      {title(r.profession)}
                    </button>
                    <Hire row={r} source={source} label="Tier estimates" />
                  </td>
                  <td>
                    <Money copper={r.estimate.cost_copper ?? null} />
                  </td>
                  <td>
                    <Money copper={r.best?.profit_copper ?? null} />
                  </td>
                  <td>
                    {r.holders.length
                      ? r.holders.map((h) => (
                          <div key={h.character.join("|")}>
                            <CharacterName character={h.character} /> ·{" "}
                            {h.rank ?? "unknown"}/{h.max_rank ?? "unknown"}
                          </div>
                        ))
                      : "No evidenced holder"}
                  </td>
                  <td>
                    <EstimatePill estimate={r.estimate} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel
        title="Instead of a new hire"
        subtitle={`Best reachable per craft · within ${window} points`}
      >
        <div className={styles.scroll}>
          <table>
            <thead>
              <tr>
                <th>Profession</th>
                <th>Best per craft in reach</th>
                <th>Team holder</th>
                <th>Estimate</th>
              </tr>
            </thead>
            <tbody>
              {data.comparisons.flatMap((c) =>
                c.professions.map((p) => (
                  <tr key={c.character.join("|") + p.profession}>
                    <th>
                      <button
                        onClick={() => inspect({ profession: p.profession })}
                      >
                        {title(p.profession)}
                      </button>
                    </th>
                    <td>
                      <Money copper={p.best?.profit_copper ?? null} />
                    </td>
                    <td>
                      <CharacterName character={c.character} />
                    </td>
                    <td>
                      <EstimatePill estimate={p.best?.estimate} />
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
          {!data.comparisons.length && (
            <p>No character has two evidenced primary professions.</p>
          )}
        </div>
      </Panel>
    </>
  );
}
