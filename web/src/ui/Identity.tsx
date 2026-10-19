import { Pill, Tip } from "./parts";
// Plain words, shown only beside another identity of the same item (ADDON-08 keeps them apart).
export function Identity({
  state,
  several,
}: {
  state: string | null | undefined;
  several: boolean;
}) {
  if (state === "base" || !several) return null;
  const label =
    state === "unresolved" ? "unidentified link" : (state ?? "legacy");
  const explanation =
    label === "variant"
      ? "This stat-changing variant has separate listings and prices; it never pools with the base item or another variant."
      : label === "unidentified link"
        ? "Missing or unsupported item-link evidence. Listings stay separate and never enter base-item crafting or depth calculations."
        : "Older scan without variant evidence. Historical prices are preserved without assigning a variant.";
  return (
    <Tip text={explanation}>
      <Pill>{label}</Pill>
    </Tip>
  );
}
