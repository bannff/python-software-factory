// AG-UI Event Types

export type AGUIEventType =
  | "RUN_STARTED" | "RUN_FINISHED" | "RUN_ERROR"
  | "STEP_STARTED" | "STEP_FINISHED"
  | "TEXT_MESSAGE_START" | "TEXT_MESSAGE_CONTENT" | "TEXT_MESSAGE_END"
  | "TOOL_CALL_START" | "TOOL_CALL_ARGS" | "TOOL_CALL_END"
  | "STATE_SNAPSHOT" | "STATE_DELTA" | "MESSAGES_SNAPSHOT" | "CUSTOM";

interface BaseEvent { timestamp: number; }

export interface RunStartedEvent extends BaseEvent {
  type: "RUN_STARTED"; threadId: string; runId: string;
}
export interface RunFinishedEvent extends BaseEvent {
  type: "RUN_FINISHED"; threadId: string; runId?: string;
}
export interface RunErrorEvent extends BaseEvent {
  type: "RUN_ERROR"; message: string;
}
export interface StepStartedEvent extends BaseEvent {
  type: "STEP_STARTED"; stepName: string;
}
export interface StepFinishedEvent extends BaseEvent {
  type: "STEP_FINISHED"; stepName: string;
}
export interface TextMessageStartEvent extends BaseEvent {
  type: "TEXT_MESSAGE_START"; messageId: string; role: "assistant" | "user" | "system";
}
export interface TextMessageContentEvent extends BaseEvent {
  type: "TEXT_MESSAGE_CONTENT"; messageId: string; delta: string;
}
export interface TextMessageEndEvent extends BaseEvent {
  type: "TEXT_MESSAGE_END"; messageId: string;
}
export interface ToolCallStartEvent extends BaseEvent {
  type: "TOOL_CALL_START"; toolCallId: string; toolCallName: string;
}
export interface ToolCallArgsEvent extends BaseEvent {
  type: "TOOL_CALL_ARGS"; toolCallId: string; delta: string;
}
export interface ToolCallEndEvent extends BaseEvent {
  type: "TOOL_CALL_END"; toolCallId: string; result?: string;
}
export interface StateSnapshotEvent extends BaseEvent {
  type: "STATE_SNAPSHOT"; snapshot: Record<string, unknown>;
}
export interface JsonPatchOp {
  op: "add" | "remove" | "replace" | "move" | "copy" | "test";
  path: string; value?: unknown; from?: string;
}
export interface StateDeltaEvent extends BaseEvent {
  type: "STATE_DELTA"; delta: JsonPatchOp[];
}
export interface MessagesSnapshotEvent extends BaseEvent {
  type: "MESSAGES_SNAPSHOT"; messages: import("./chat").ChatMessage[];
}
export interface CustomEvent extends BaseEvent {
  type: "CUSTOM"; name: string; value: unknown;
}

export type AGUIEvent =
  | RunStartedEvent | RunFinishedEvent | RunErrorEvent
  | StepStartedEvent | StepFinishedEvent
  | TextMessageStartEvent | TextMessageContentEvent | TextMessageEndEvent
  | ToolCallStartEvent | ToolCallArgsEvent | ToolCallEndEvent
  | StateSnapshotEvent | StateDeltaEvent | MessagesSnapshotEvent | CustomEvent;
