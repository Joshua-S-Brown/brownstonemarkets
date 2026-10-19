import type { ReactNode } from "react";
import { useInspector } from "../../app/InspectorContext";
import { moneyText } from "../../ui/Money";
import { CharacterName } from "../../ui/CharacterName";
import { Tip } from "../../ui/parts";
import { Icon } from "../../ui/Icon";
import { Money } from "./Money";
import { title } from "./Hiring";
import { NextStep } from "./Path";
import type { Member } from "./types";
import styles from "./team.module.css";

export function skillFraction(rank: number | null, maximum: number | null) {
  return rank == null || maximum == null || maximum <= 0
    ? null
    : Math.max(0, Math.min(1, rank / maximum));
}
export function SkillBar({
  name,
  rank,
  maximum,
  label,
}: {
  name: string;
  rank: number | null;
  maximum: number | null;
  label?: ReactNode;
}) {
  const fraction = skillFraction(rank, maximum);
  return (
    <div className={styles.skill}>
      <div>
        {label ?? name}
        <span>
          {rank ?? "unknown"} / {maximum ?? "unknown"}
        </span>
      </div>
      {fraction != null && (
        <div
          className={styles.bar}
          role="progressbar"
          aria-label={name}
          aria-valuemin={0}
          aria-valuemax={maximum!}
          aria-valuenow={rank!}
        >
          <i style={{ width: `${fraction * 100}%` }} />
          <b title={`Next tier: ${maximum}`} />
        </div>
      )}
    </div>
  );
}
export function MemberCard({ member }: { member: Member }) {
  const { character, card, progression } = member;
  const inspect = useInspector();
  const best = progression.best_step;
  const suggestion = member.suggestions[0];
  const evidence = progression.professions
    .map(
      (g) =>
        `${g.profession}: ${g.best ? `${g.best.name} · +${g.best.points_needed} points · ${moneyText(g.best.profit_copper)} per craft · reach ${moneyText(g.best.estimate.cost_copper ?? null)} · ${g.best.estimate.complete ? "complete" : g.best.estimate.reasons?.join("; ") || "incomplete"}` : g.note || "no valued recipe in reach"}`,
    )
    .join("\n");
  return (
    <article
      className={styles.card}
      onClick={(event) => {
        if (!(event.target as HTMLElement).closest("button,a,summary"))
          inspect({ character });
      }}
    >
      <header>
        <div>
          <CharacterName character={character} avatar />
          <div className={styles.meta}>
            Level {card.level ?? "unknown"} · seen {card.last_seen_relative}
            {card.stale ? " · stale" : ""}
          </div>
        </div>
        <Money copper={card.gold_copper} />
      </header>
      {card.professions.map((p) => (
        <div key={p.name}>
          <SkillBar name={p.name} rank={p.rank} maximum={p.max_rank} />
          {p.at_cap && <small>At cap: train the next tier</small>}
        </div>
      ))}
      <div className={styles.action}>
        <div className={styles.step}>
          <Icon name="arrow" />
          {best?.best ? (
            <NextStep group={best} />
          ) : suggestion ? (
            <p>
              Take up {title(suggestion.profession)}:{" "}
              {suggestion.best_now ? (
                <>
                  <Money copper={suggestion.best_now.profit_copper} /> per craft
                  now
                </>
              ) : (
                "nothing priced within the selected window"
              )}
              , <Money copper={suggestion.best?.profit_copper ?? null} /> at 300
            </p>
          ) : member.suggestion_note ? (
            <p>{member.suggestion_note}</p>
          ) : best ? (
            <NextStep group={best} />
          ) : (
            <p>Next step · current scan unavailable</p>
          )}
        </div>
        <Tip
          text={`${card.last_seen_utc} · ${card.machine ?? "machine unknown"}\n${evidence}`}
        >
          All next steps and evidence
        </Tip>
      </div>
    </article>
  );
}
