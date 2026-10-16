import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { post } from "../../api/client";
import { Money } from "../../ui/Money";
import type { components } from "../../api/schema";
import styles from "../../theme/app.module.css";
type Target = components["schemas"]["Target"];
export function Targets({
  source,
  entries,
  names,
}: {
  source: string;
  entries: Target[];
  names: Record<string, string>;
}) {
  const [open, setOpen] = useState(false),
    [draft, setDraft] = useState(entries);
  const [id, setId] = useState(""),
    [units, setUnits] = useState(""),
    [limit, setLimit] = useState(""),
    [mode, setMode] = useState("none");
  const [message, setMessage] = useState(""),
    [saving, setSaving] = useState(false);
  const client = useQueryClient();
  function update() {
    if (
      !/^\d+$/.test(id) ||
      Number(id) <= 0 ||
      !/^\d+$/.test(units) ||
      (mode !== "none" && (!/^\d+$/.test(limit) || Number(limit) <= 0))
    ) {
      setMessage(
        "Draft rejected: enter a positive item ID, nonnegative units and a positive limit.",
      );
      return;
    }
    setDraft([
      ...draft.filter((e) => e.item_id !== Number(id)),
      {
        item_id: Number(id),
        target_units: Number(units),
        buy_copper: mode === "copper" ? Number(limit) : null,
        buy_percent: mode === "percent" ? Number(limit) : null,
      },
    ]);
    setMessage("Draft updated; Save to keep it.");
  }
  async function save() {
    setSaving(true);
    try {
      await post("ledger/targets", source, { entries: draft });
      await client.invalidateQueries({ queryKey: [source, "ledger"] });
      setOpen(false);
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(v) => {
        if (v) {
          setDraft(entries.map((e) => ({ ...e })));
          setMessage("");
          setId("");
          setUnits("");
          setLimit("");
          setMode("none");
        }
        setOpen(v);
      }}
    >
      <Dialog.Trigger className={styles["primary"]}>
        Set stock targets
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className={styles["shade"]} />
        <Dialog.Content
          className={`${styles["inspector"]} ${styles["target-form"]}`}
          aria-describedby={undefined}
        >
          <Dialog.Title>Stock targets</Dialog.Title>
          <Dialog.Close>Close ✕</Dialog.Close>
          <p>
            Team totals. Update and Remove change this draft. Save applies all
            draft changes.
          </p>
          <label>
            Item ID
            <input value={id} onChange={(e) => setId(e.target.value)} />
          </label>
          <label>
            Target units
            <input value={units} onChange={(e) => setUnits(e.target.value)} />
          </label>
          <label>
            Buy limit
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="none">No limit</option>
              <option value="copper">Fixed copper</option>
              <option value="percent">Market value percent</option>
            </select>
          </label>
          <label>
            Limit (integer copper or percent)
            <input value={limit} onChange={(e) => setLimit(e.target.value)} />
          </label>
          <button onClick={update}>Update draft</button>
          <button
            onClick={() => {
              if (!/^\d+$/.test(id) || Number(id) <= 0)
                setMessage("Enter an item ID to remove its target.");
              else setDraft(draft.filter((e) => e.item_id !== Number(id)));
            }}
          >
            Remove target from draft
          </button>
          <p role="status">{message}</p>
          {draft.map((e) => (
            <p key={e.item_id}>
              {names[e.item_id] ?? `Item ${e.item_id}`} ({e.item_id}):{" "}
              {e.target_units} units ·{" "}
              {e.buy_percent != null ? (
                `${e.buy_percent}% of this scan’s market value`
              ) : e.buy_copper != null ? (
                <>
                  <Money copper={e.buy_copper} /> / unit
                </>
              ) : (
                "No buy limit"
              )}
            </p>
          ))}
          <button
            className={styles["primary"]}
            disabled={saving}
            onClick={() => void save()}
          >
            Save targets
          </button>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
