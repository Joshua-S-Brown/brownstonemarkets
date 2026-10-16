const key = (source: string) => "brownstone-team-" + source;
export function readWindow(source: string): number {
  try {
    const value: unknown = JSON.parse(
      sessionStorage.getItem(key(source)) || "25",
    );
    return typeof value === "number" &&
      Number.isInteger(value) &&
      value >= 5 &&
      value <= 100
      ? value
      : 25;
  } catch {
    return 25;
  }
}
export function writeWindow(source: string, value: number) {
  try {
    sessionStorage.setItem(key(source), JSON.stringify(value));
  } catch {
    // Storage unavailable: the window still applies for this page.
  }
}
