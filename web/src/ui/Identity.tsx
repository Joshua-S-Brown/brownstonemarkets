import { Pill, Tip } from "./parts";
export function Identity({ state }: { state: string | null | undefined }) {
  if (state === "base") return null;
  const label = state ?? "legacy";
  const explanation =
    label === "variant"
      ? "This stat-changing variant has separate listings and prices; it never pools with the base item or another variant."
      : label === "unresolved"
        ? "Missing or unsupported item-link evidence. Listings stay separate and never enter base-item crafting or depth calculations."
        : "Older scan without variant evidence. Historical prices are preserved without assigning a variant.";
  return (
    <Tip text={explanation}>
      <Pill>{label}</Pill>
    </Tip>
  );
}
