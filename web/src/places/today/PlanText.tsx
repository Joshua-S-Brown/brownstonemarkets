import { Money } from "../../ui/Money";
// Queue/session prose already comes from money.format_money. Colour its coin tokens
// with the shared renderer without changing the supplied wording or plan amounts.
export function PlanText({ text }: { text: string }) {
  return (
    <>
      {text.split(/(-?[\d,]+[gsc]\b)/g).map((part, i) => {
        if (!/^-?[\d,]+[gsc]$/.test(part)) return part;
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
