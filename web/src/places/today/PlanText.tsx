import { ConfidencePill } from "../../ui/ConfidencePill";
import { CharacterWords } from "../../ui/CharacterWords";
import type { CharacterKey } from "../../app/InspectorContext";
import { EvidenceTip } from "../../ui/Evidence";
import { Money } from "../../ui/Money";
// Queue/session words and copper amounts stay unchanged; recipe identity is on demand.
export function PlanText({
  text,
  characters = [],
}: {
  text: string;
  characters?: CharacterKey[];
}) {
  return (
    <>
      {text
        .split(
          /((?:High|Medium|Low) confidence \([^)]+\)|recipe \d+ \([^)]+\)|-?[\d,]+[gsc]\b)/gi,
        )
        .map((part, i) => {
          const confidence = part.match(
            /^(High|Medium|Low) confidence \((.+)\)$/i,
          );
          if (confidence)
            return (
              <ConfidencePill
                key={i}
                level={confidence[1]}
                reasons={[confidence[2]]}
              />
            );
          if (/^recipe \d+ \(/i.test(part))
            return (
              <EvidenceTip key={i} label="recipe" data={{ recipe: part }} />
            );
          if (!/^-?[\d,]+[gsc]$/.test(part))
            return (
              <CharacterWords key={i} text={part} characters={characters} />
            );
          const unit = part.slice(-1),
            amount = Number(part.slice(0, -1).replaceAll(",", ""));
          return (
            <Money
              key={i}
              copper={amount * (unit === "g" ? 10000 : unit === "s" ? 100 : 1)}
            />
          );
        })}
    </>
  );
}
