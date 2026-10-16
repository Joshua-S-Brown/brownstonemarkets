export type Days = "7" | "30" | "all";
export function readDays(source: string): Days {
  try {
    const v = sessionStorage.getItem("brownstone-ledger-" + source);
    return v === "30" || v === "all" ? v : "7";
  } catch {
    return "7";
  }
}
export function writeDays(source: string, days: Days) {
  try {
    sessionStorage.setItem("brownstone-ledger-" + source, days);
  } catch {
    /* Applies for this page when storage is unavailable. */
  }
}
