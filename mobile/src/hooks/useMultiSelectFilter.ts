import { useCallback, useMemo, useState } from 'react';

export function formatFilterLabel(selected: string[]): string {
  if (selected.length === 0) return '전체';
  if (selected.length === 1) return selected[0];
  return `${selected[0]} 외 ${selected.length - 1}`;
}

export function useMultiSelectFilter(initial: string[] = []) {
  const [selected, setSelected] = useState<string[]>(initial);

  const toggle = useCallback((option: string) => {
    if (option === '전체') {
      setSelected([]);
      return;
    }
    setSelected((prev) =>
      prev.includes(option) ? prev.filter((x) => x !== option) : [...prev, option],
    );
  }, []);

  const reset = useCallback(() => setSelected([]), []);

  const prune = useCallback((valid: string[]) => {
    setSelected((prev) => prev.filter((x) => valid.includes(x)));
  }, []);

  const isActive = useCallback(
    (option: string) => (option === '전체' ? selected.length === 0 : selected.includes(option)),
    [selected],
  );

  const matches = useCallback(
    (value: string) => selected.length === 0 || selected.includes(value),
    [selected],
  );

  const label = useMemo(() => formatFilterLabel(selected), [selected]);

  return { selected, toggle, reset, prune, isActive, matches, label };
}
