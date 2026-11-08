"use client";

import { createContext, useContext } from "react";

export interface MutationRefresh {
  /** Bumps after every successful mutation; views re-read their data when it changes. */
  version: number;
  /** Call after a successful mutation so summaries and sibling panels refetch. */
  notify: () => void;
}

const NOOP: MutationRefresh = { version: 0, notify: () => undefined };

export const MutationRefreshContext = createContext<MutationRefresh>(NOOP);

/** Outside a Refreshable this is a no-op, so panels still work standalone. */
export function useMutationRefresh(): MutationRefresh {
  return useContext(MutationRefreshContext);
}
