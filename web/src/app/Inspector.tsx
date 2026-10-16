import styles from "../theme/app.module.css";
import { useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { InspectorContext, type RecordRef } from "./InspectorContext";
import { ItemRecord } from "../records/ItemRecord";
export function Inspector({
  source,
  children,
}: {
  source: string;
  children: ReactNode;
}) {
  const [params, setParams] = useSearchParams();
  const [stack, setStack] = useState<RecordRef[]>([]);
  const [character, setCharacter] = useState<string | null>(null);
  const id = Number(params.get("inspect"));
  const current: RecordRef | null = character
    ? { character }
    : Number.isSafeInteger(id) && id > 0
      ? { item: id }
      : null;
  function show(record: RecordRef | null) {
    setCharacter(record && "character" in record ? record.character : null);
    const next = new URLSearchParams(params);
    if (record && "item" in record) next.set("inspect", String(record.item));
    else next.delete("inspect");
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
              {stack.length > 0 && <button onClick={back}>← Back</button>}
              <Dialog.Close>Close ✕</Dialog.Close>
            </div>
            {current &&
              ("item" in current ? (
                <ItemRecord
                  key={source + current.item}
                  id={current.item}
                  source={source}
                />
              ) : (
                <>
                  <h1>{current.character}</h1>
                  <p>Character records will come from Team (STORY-084).</p>
                </>
              ))}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </InspectorContext.Provider>
  );
}
