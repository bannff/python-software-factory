import { FolderX, MessageSquareOff, ShieldAlert, Unplug, Archive, type LucideIcon } from "lucide-react";

/** Stable failure codes `devtools_*` tools raise (TypedToolFailure, #82). */
export interface FilesState { icon: LucideIcon; text: string }

const STATES: Record<string, FilesState> = {
  devtools_session_required: { icon: MessageSquareOff, text: "Start a chat to browse files." },
  devtools_session_unavailable: { icon: Archive, text: "This chat’s session is gone." },
  devtools_project_unbound: { icon: FolderX, text: "No project is bound to this chat." },
  devtools_binding_unavailable: { icon: Unplug, text: "The project’s files can’t be reached." },
  devtools_path_refused: { icon: ShieldAlert, text: "That path is outside the workspace." },
};

/** The short state for a known code; undefined lets callers show the raw reason. */
export function filesState(reason: string | undefined): FilesState | undefined {
  return reason ? STATES[reason] : undefined;
}
