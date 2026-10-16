import { createContext, useContext } from "react";
export type RecordRef =
  | { item: number; variant?: string }
  | { character: string };
export const InspectorContext = createContext<(record: RecordRef) => void>(
  () => {},
);
export const useInspector = () => useContext(InspectorContext);
