import { Money as CopperMoney } from "../../ui/Money";
export function Money({ copper }: { copper: number | null }) {
  return copper == null ? <>unknown</> : <CopperMoney copper={copper} />;
}
