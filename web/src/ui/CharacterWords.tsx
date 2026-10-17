import { Fragment } from "react";
import type { CharacterKey } from "../app/InspectorContext";
import { CharacterName } from "./CharacterName";
/** Link only identities explicitly supplied by this source; ambiguous short names stay prose. */
export function CharacterWords({
  text,
  characters,
}: {
  text: string;
  characters: CharacterKey[];
}) {
  const names = new Map<string, CharacterKey>();
  for (const key of characters) {
    names.set(key.join(" · "), key);
    if (characters.filter((c) => c[0] === key[0]).length === 1)
      names.set(key[0], key);
  }
  if (!names.size) return <>{text}</>;
  const alternatives = [...names.keys()]
    .sort((a, b) => b.length - a.length)
    .map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return (
    <>
      {text
        .split(
          new RegExp(
            `(?<![\\p{L}\\p{N}])(${alternatives.join("|")})(?![\\p{L}\\p{N}])`,
            "u",
          ),
        )
        .map((part, i) => (
          <Fragment key={i}>
            {names.has(part) ? (
              <CharacterName character={names.get(part)!} />
            ) : (
              part
            )}
          </Fragment>
        ))}
    </>
  );
}
