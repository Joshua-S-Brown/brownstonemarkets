const paths = {
  today: "M4 5h16M4 12h10M4 19h7M17 15l2 2 4-4",
  market: "M3 17l5-6 4 3 5-7 4 4M3 21h18",
  chain: "M5 6h4v4H5zM15 14h4v4h-4zM9 8h3a2 2 0 012 2v4a2 2 0 002 2",
  team: "M8 11a3 3 0 100-6 3 3 0 000 6zM2 20c0-3 3-5 6-5s6 2 6 5M16 11a3 3 0 100-6M18 15c2.5.5 4 2.3 4 5",
  ledger: "M4 4h16v16H4zM4 9h16M9 9v11",
  data: "M12 3c5 0 8 1.3 8 3s-3 3-8 3-8-1.3-8-3 3-3 8-3zM4 6v6c0 1.7 3 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3 3 8 3s8-1.3 8-3v-6",
  search: "M11 18a7 7 0 110-14 7 7 0 010 14zM21 21l-5-5",
  x: "M6 6l12 12M18 6L6 18",
  back: "M15 18l-6-6 6-6",
  moon: "M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z",
  info: "M12 8h.01M11 12h1v5h1M12 21a9 9 0 110-18 9 9 0 010 18z",
  check: "M5 12l5 5 9-10",
  plus: "M12 5v14M5 12h14",
  arrow: "M5 12h14M13 6l6 6-6 6",
  up: "M6 15l6-6 6 6",
  down: "M6 9l6 6 6-6",
};
export function Icon({ name }: { name: keyof typeof paths }) {
  return (
    <svg
      width={18}
      height={18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}
