import { createContext, useContext } from "react";
export type RecordRef = { item: number } | { character: string };
export const InspectorContext = createContext<(record: RecordRef) => void>(
  () => {},
);
export const useInspector = () => useContext(InspectorContext);
