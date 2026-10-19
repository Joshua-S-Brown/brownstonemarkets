import { createContext, useContext } from "react";
export type CharacterKey = [string, string, string];
export type RecordRef =
  | { item: number; variant?: string }
  | { character: CharacterKey }
  | { profession: string };
export const InspectorContext = createContext<(record: RecordRef) => void>(
  () => {},
);
export const useInspector = () => useContext(InspectorContext);
