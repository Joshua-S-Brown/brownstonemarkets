import type { ReactNode } from "react";
import type { components } from "../../api/schema";
import { Money } from "./Money";
import { CharacterName } from "../../ui/CharacterName";
import { Panel } from "../../ui/Panel";
import { Tile } from "../../ui/Tile";
import { UtcTime } from "../../ui/UtcTime";
import { Evidence } from "../../ui/Evidence";
import styles from "./team.module.css";
import record from "../../records/records.module.css";

type Row = components["schemas"]["EarningsRow"];
type Character = components["schemas"]["CharacterEarnings"];
type Report = components["schemas"]["Earnings"];

function Rates({
  rows,
}: {
  rows: (Omit<Row, "label"> & { label: ReactNode })[];
}) {
  return (
    <div className={styles.scroll}>
      <table className={styles.earnings}>
        <caption>Measured earnings per hour</caption>
        <thead>
          <tr>
            <th>Evidence</th>
            <th>World gold/hour</th>
            <th>Loot value/hour</th>
            <th>XP/hour of world time</th>
            <th>Market gold/hour</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <th>
                {r.label}
                <p>
                  {(r.seconds / 60).toFixed(1)} minutes
                  {r.thin && " · thin evidence (under 30 minutes)"}
                  <br />
                  {(r.world_seconds / 60).toFixed(1)} world ·{" "}
                  {(r.market_seconds / 60).toFixed(1)} market min
                </p>
              </th>
              <td>
                <Money copper={r.world_per_hour_copper} />
              </td>
              <td>
                {r.unpriced_units > 0 &&
                  r.loot_per_hour_copper !== null &&
                  "at least "}
                <Money copper={r.loot_per_hour_copper} />
                <p>
                  value if sold, not gold
                  {r.unpriced_units > 0 &&
                    ` · ${r.unpriced_units} units without a price`}
                </p>
              </td>
              <td>
                {r.xp_label === "XP not captured" ? (
                  r.xp_label
                ) : (
                  <>
                    {r.xp_label === "at least" && "at least "}
                    {r.xp_per_hour ?? "unknown"}
                  </>
                )}
              </td>
              <td>
                <Money copper={r.market_per_hour_copper} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Debrief({
  session: s,
}: {
  session: components["schemas"]["EarningsSession"];
}) {
  return (
    <>
      <p>
        <UtcTime value={new Date(s.start * 1000).toISOString()} /> –{" "}
        <UtcTime value={new Date(s.end * 1000).toISOString()} /> ·{" "}
        {s.machine ?? "machine unknown"}
      </p>
      <div className={record.facts}>
        <Tile
          label="World time"
          value={`${(s.world_seconds / 60).toFixed(1)} min`}
        />
        <Tile
          label="Market time"
          value={`${(s.market_seconds / 60).toFixed(1)} min`}
        />
        <Tile label="World gold" value={<Money copper={s.world_copper} />} />
        <Tile label="Market gold" value={<Money copper={s.market_copper} />} />
        <Tile
          label="Loot value"
          value={
            <>
              {s.unpriced_units > 0 && s.loot_copper > 0 && "at least "}
              <Money
                copper={
                  s.unpriced_units > 0 && s.loot_copper === 0
                    ? null
                    : s.loot_copper
                }
              />
            </>
          }
          caption={`value if sold, not gold${s.unpriced_units > 0 ? ` · ${s.unpriced_units} units without a price` : ""}`}
        />
        <Tile
          label="XP"
          value={
            s.xp_label === "XP not captured"
              ? "—"
              : `${s.xp_label === "at least" ? "at least " : ""}${s.quest_xp + s.other_xp}`
          }
          caption={
            s.xp_label === "XP not captured"
              ? "XP not captured"
              : `${s.quest_xp} quest XP · ${s.other_xp} other XP recorded${s.xp_label === "at least" ? " (incomplete)" : ""} · ${s.levels} levels gained`
          }
        />
      </div>
      <h4>Gold by category</h4>
      {!Object.keys(s.categories).length && <p>No gold movements captured.</p>}
      {Object.entries(s.groups).map(
        ([group, categories]) =>
          Object.keys(categories).length > 0 && (
            <section key={group} aria-label={`${group} gold`}>
              <h5>
                {group === "not assigned"
                  ? "Not assigned to an activity"
                  : `${group[0].toUpperCase()}${group.slice(1)} gold`}
              </h5>
              {Object.entries(categories).map(([category, copper]) => (
                <p key={category}>
                  {category} · <Money copper={copper} />
                </p>
              ))}
            </section>
          ),
      )}
      <p>
        Excluded own mail · <Money copper={s.own_mail_copper} />
      </p>
    </>
  );
}

export function CharacterEarnings({ data }: { data: Character }) {
  const last = data.sessions.at(-1);
  return (
    <Panel title="Is it paying off?">
      <p>
        Your own past sessions, not a promise; launch competition differs.
        Market gold includes sales of items gathered or crafted earlier; no cost
        basis yet.
      </p>
      <h3>Last session</h3>
      {last ? (
        <Debrief session={last} />
      ) : (
        <p>No sessions captured. Import journal evidence in Data.</p>
      )}
      <h3>By level band</h3>
      <Rates rows={data.bands} />
      {data.sessions.length > 1 && (
        <details>
          <summary>Earlier sessions</summary>
          {data.sessions
            .slice(0, -1)
            .reverse()
            .map((s, i) => (
              <section key={i}>
                <Debrief session={s} />
              </section>
            ))}
        </details>
      )}
      <details>
        <summary>Time and earnings evidence</summary>
        <Evidence data={data} />
      </details>
    </Panel>
  );
}

export function TeamEarnings({ data }: { data: Report }) {
  return (
    <Panel title="Is it paying off?">
      <p>{data.caveat}</p>
      <p>Open a character for the last session and five-level bands.</p>
      <Rates
        rows={[
          ...data.characters.map((c) => ({
            ...c.total,
            label: <CharacterName character={c.character} />,
          })),
          data.total,
        ]}
      />
      <p>
        {data.excluded_money} money entries without baselines ·{" "}
        {data.unknown_login_entries} entries without a login marker excluded.
      </p>
    </Panel>
  );
}
