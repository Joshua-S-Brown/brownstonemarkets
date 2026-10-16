import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { moneyText } from "../../ui/Money";
import { post } from "../../api/client";
import { type Plan, todayKey } from "./state";
import styles from "../../theme/app.module.css";
export function Settings({ source, data }: { source: string; data: Plan }) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger aria-label="Today settings">⚙ Settings</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.shade} />
        <Dialog.Content
          className={styles.inspector}
          aria-describedby={undefined}
        >
          <Dialog.Title>Today settings</Dialog.Title>
          <SettingsForm
            key={String(open)}
            source={source}
            data={data}
            close={() => setOpen(false)}
          />
          <Dialog.Close>Cancel</Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
function SettingsForm({
  source,
  data,
  close,
}: {
  source: string;
  data: Plan;
  close: () => void;
}) {
  const [draft, setDraft] = useState<
    Plan["settings"] & { gold_text: string; minimum_text: string }
  >({
    ...data.settings,
    gold_text: moneyText(Number(data.settings.gold_copper)),
    minimum_text: moneyText(Number(data.settings.minimum_copper)),
  });
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => post("today/settings", source, { settings: draft }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: todayKey(source) });
      close();
    },
  });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate();
      }}
    >
      <label>
        Character{" "}
        <select
          value={draft.character ? JSON.stringify(draft.character) : ""}
          onChange={(e) =>
            setDraft({
              ...draft,
              character: e.target.value
                ? (JSON.parse(e.target.value) as string[])
                : null,
            })
          }
        >
          <option value="">Our team</option>
          {data.characters.map((c) => (
            <option key={c.join("|")} value={JSON.stringify(c)}>
              {c.join(" · ")}
            </option>
          ))}
        </select>
      </label>
      {["gold_override", "include_unknown"].map((k) => (
        <label key={k}>
          <input
            type="checkbox"
            checked={Boolean(draft[k])}
            onChange={(e) => setDraft({ ...draft, [k]: e.target.checked })}
          />
          {k === "gold_override"
            ? "Enter an amount instead"
            : "Include unknown recipes"}
        </label>
      ))}
      <label>
        Minimum mode{" "}
        <select
          value={String(draft.mode)}
          onChange={(e) => setDraft({ ...draft, mode: e.target.value })}
        >
          <option value="scaled">Scaled</option>
          <option value="fixed">Fixed</option>
        </select>
      </label>
      {(["gold_text", "minimum_text"] as const).map((k) => (
        <label key={k}>
          {k === "gold_text" ? "Entered gold" : "Minimum gain"}
          <input
            required
            value={draft[k]}
            onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
          />
        </label>
      ))}
      <label>
        Most crafts per item
        <input
          required
          type="number"
          step={1}
          min={1}
          max={1000}
          value={Number(draft.max_crafts)}
          onChange={(e) =>
            setDraft({ ...draft, max_crafts: Number(e.target.value) })
          }
        />
      </label>
      {draft.mode === "scaled" && (
        <>
          <label>
            Percentage of gold available
            <input
              required
              type="number"
              step={0.01}
              min={0}
              max={100}
              value={Number(draft.percent_basis_points) / 100}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  percent_basis_points: Math.round(
                    Number(e.target.value) * 100,
                  ),
                })
              }
            />
          </label>
          <p>
            Use the larger of the fixed minimum and this percentage of available
            gold.
          </p>
        </>
      )}
      <label>
        Post duration{" "}
        <select
          value={Number(draft.post_duration_hours)}
          onChange={(e) =>
            setDraft({ ...draft, post_duration_hours: Number(e.target.value) })
          }
        >
          {[2, 8, 24].map((h) => (
            <option key={h} value={h}>
              {h} hours
            </option>
          ))}
        </select>
      </label>
      {mutation.error && <p role="alert">{mutation.error.message}</p>}
      <button type="submit" disabled={mutation.isPending}>
        Save Today settings
      </button>
    </form>
  );
}
