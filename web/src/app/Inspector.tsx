import styles from "../theme/app.module.css";
import { lazy, Suspense, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import {
  InspectorContext,
  type CharacterKey,
  type RecordRef,
} from "./InspectorContext";
import { Origin } from "./Origin";
import { ItemRecord } from "../records/ItemRecord";
const CharacterRecord = lazy(() =>
  import("../records/CharacterRecord").then((m) => ({
    default: m.CharacterRecord,
  })),
);
export function Inspector({
  source,
  children,
}: {
  source: string;
  children: ReactNode;
}) {
  const [params, setParams] = useSearchParams();
  const [stack, setStack] = useState<RecordRef[]>([]);
  const [character, setCharacter] = useState<CharacterKey | null>(null);
  const id = Number(params.get("inspect"));
  const current: RecordRef | null = character
    ? { character }
    : Number.isSafeInteger(id) && id > 0
      ? {
          item: id,
          ...(params.get("variant") ? { variant: params.get("variant")! } : {}),
        }
      : null;
  function show(record: RecordRef | null) {
    setCharacter(record && "character" in record ? record.character : null);
    const next = new URLSearchParams(params);
    if (record && "item" in record) next.set("inspect", String(record.item));
    else next.delete("inspect");
    if (record && "item" in record && record.variant)
      next.set("variant", record.variant);
    else next.delete("variant");
    setParams(next, { replace: true });
  }
  function open(record: RecordRef) {
    if (current && JSON.stringify(current) === JSON.stringify(record)) return;
    if (current) setStack((previous) => [...previous, current]);
    show(record);
  }
  function back() {
    show(stack.at(-1) ?? null);
    setStack((previous) => previous.slice(0, -1));
  }
  return (
    <InspectorContext.Provider value={open}>
      {children}
      <Dialog.Root
        open={!!current}
        onOpenChange={(value) => {
          if (!value) {
            show(null);
            setStack([]);
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className={styles["shade"]} />
          <Dialog.Content
            className={styles["inspector"]}
            aria-describedby={undefined}
          >
            <Dialog.Title className={styles["sr-only"]}>
              Record inspector
            </Dialog.Title>
            <div className={styles["record-actions"]}>
              {stack.length === 0 && <Origin source={source} />}
              {stack.length > 0 && <button onClick={back}>← Back</button>}
              <Dialog.Close>Close ✕</Dialog.Close>
            </div>
            {current &&
              ("item" in current ? (
                <ItemRecord
                  key={source + current.item + current.variant}
                  id={current.item}
                  variant={current.variant}
                  source={source}
                />
              ) : (
                <Suspense fallback={<p role="status">Loading character…</p>}>
                  <CharacterRecord
                    key={source + current.character.join("|")}
                    source={source}
                    character={current.character}
                  />
                </Suspense>
              ))}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </InspectorContext.Provider>
  );
}
