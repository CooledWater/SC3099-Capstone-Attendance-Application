import { useState } from "react";

// Keep navigation/filter selections per account and browser tab, without records or tokens.
export function useSessionValue(
  key: string | undefined,
  initial: string,
): [string, (value: string) => void] {
  const [value, setValue] = useState(() => {
    try {
      return key ? (sessionStorage.getItem(key) ?? initial) : initial;
    } catch {
      return initial;
    }
  });
  return [
    value,
    (next) => {
      setValue(next);
      try {
        if (key) sessionStorage.setItem(key, next);
      } catch {
        // Navigation continues when browser storage is disabled.
      }
    },
  ];
}
