import { useInspector } from "../../app/InspectorContext";
import { CharacterName } from "../../ui/CharacterName";
import { Panel } from "../../ui/Panel";
import { Pill, Tip } from "../../ui/parts";
import { title } from "./Hiring";
import type { TeamData } from "./types";
import styles from "./team.module.css";
export function coverageRows(data: TeamData) {
  return [
    ...data.hires.map((h) => ({
      profession: h.profession,
      holders: h.holders,
    })),
    ...data.no_catalog
      .filter((n) => !data.hires.some((h) => h.profession === n))
      .map((n) => ({
        profession: n,
        holders: data.roster.flatMap((r) =>
          r.card.professions
            .filter((p) => p.name.toLowerCase() === title(n).toLowerCase())
            .map((p) => ({
              character: r.character,
              rank: p.rank,
              max_rank: p.max_rank,
            })),
        ),
      })),
  ];
}
export function Coverage({ data }: { data: TeamData }) {
  const inspect = useInspector();
  return (
    <Panel title="Profession coverage">
      <div className={styles.scroll}>
        <table>
          <thead>
            <tr>
              <th>Profession</th>
              {data.roster.map((r) => (
                <th key={r.character.join("|")}>
                  <CharacterName character={r.character} />
                </th>
              ))}
              <th>Coverage</th>
            </tr>
          </thead>
          <tbody>
            {coverageRows(data).map((r) => (
              <tr key={r.profession}>
                <th>
                  {data.no_catalog.includes(r.profession) ? (
                    <Tip text="No catalog: gathering income and supply are not modelled">
                      {title(r.profession)}
                    </Tip>
                  ) : (
                    <button
                      onClick={() => inspect({ profession: r.profession })}
                    >
                      {title(r.profession)}
                    </button>
                  )}
                </th>
                {data.roster.map((c) => {
                  const h = r.holders.find((h) =>
                    h.character.every((v, i) => v === c.character[i]),
                  );
                  return (
                    <td key={c.character.join("|")}>
                      {h ? <Pill tone="good">{h.rank ?? "unknown"}</Pill> : "·"}
                    </td>
                  );
                })}
                <td>
                  {!r.holders.length && <Pill tone="warn">Not covered</Pill>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
