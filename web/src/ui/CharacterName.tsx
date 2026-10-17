import { useInspector, type CharacterKey } from "../app/InspectorContext";
import styles from "./components.module.css";
export function CharacterName({
  character,
  avatar = false,
  onOpen,
}: {
  character: CharacterKey;
  avatar?: boolean;
  onOpen?: () => void;
}) {
  const inspect = useInspector();
  return (
    <button
      className={styles.name}
      data-avatar={avatar}
      title={`${character[1]} · ${character[2]}`}
      onClick={(event) => {
        event.stopPropagation();
        inspect({ character });
        onOpen?.();
      }}
    >
      {avatar && (
        <span aria-hidden="true" className={styles.avatar}>
          {character[0].slice(0, 2).toUpperCase()}
        </span>
      )}
      {character[0]}
    </button>
  );
}
