"use client";

import { useEffect, useState } from "react";

export interface TimelineFocusSelection {
  key: string;
  title: string;
  subtitle: string;
  entryIds: string[];
}

interface TimelineFocusStore {
  selection: TimelineFocusSelection | null;
}

type TimelineFocusListener = () => void;

const store: TimelineFocusStore = {
  selection: null,
};

const listeners = new Set<TimelineFocusListener>();

function notifyListeners() {
  for (const listener of listeners) {
    listener();
  }
}

function subscribe(listener: TimelineFocusListener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function setTimelineFocus(selection: TimelineFocusSelection | null) {
  store.selection = selection;
  notifyListeners();
}

export function useTimelineFocus() {
  const [selection, setSelection] = useState<TimelineFocusSelection | null>(store.selection);

  useEffect(() => subscribe(() => setSelection(store.selection)), []);

  return {
    selection,
    setSelection: setTimelineFocus,
    clearSelection: () => setTimelineFocus(null),
  };
}