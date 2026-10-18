import { Money } from "./Money";

/** STORY-102's display-only beta typical: a missing side says so, never 0. */
export function BetaQuote({
  copper,
  livePrice,
  ratio,
}: {
  copper: number | null | undefined;
  livePrice: number | null;
  ratio: { [key: string]: number } | null | undefined;
}) {
  return (
    <>
      {copper == null ? "no beta price" : <Money copper={copper} />}
      {livePrice === null && " · no live price"}
      {ratio &&
        ` · ${((100 * ratio.numerator) / ratio.denominator).toFixed(1)}% of beta`}
    </>
  );
}
