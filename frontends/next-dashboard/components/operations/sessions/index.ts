/**
 * M7 Option A Sessions surface — public integration API.
 *
 * The Canvas integrator mounts `SessionsView` for its view id and wires the
 * runtime-owned handlers (`onResumeSession`, `onCreateSession`) plus the live
 * `activeThreadId`, exactly mirroring SessionDeck's agent/thread binding —
 * this surface never owns that runtime state itself. `focusSessionId` +
 * `onFocusHandled` support deep-link focus of the detail heading.
 */
export { default as SessionsView, type SessionsViewProps } from "./sessions-view";
export { renameSession, archiveSession, reopenSession } from "./session-actions";
export { agentLabel, isArchived, relativeTime } from "./session-format";
