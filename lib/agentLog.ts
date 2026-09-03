"use client";

/** In-memory ring buffer for the Self-Healing Agent fallback engine.
 * The API layer and WebSocket hooks push entries whenever a transaction is
 * rerouted or recovered; SelfHealingLog.tsx subscribes and renders them. */

export interface AgentLogEntry {
  id: number;
  at: string;
  agent: string;
  severity: "info" | "warn" | "recovered";
  route: string;
  detail: string;
  latencyMs?: number;
}

const MAX_ENTRIES = 40;
let entries: AgentLogEntry[] = [];
let nextId = 1;
const listeners = new Set<(current: AgentLogEntry[]) => void>();

export function pushAgentLog(entry: Omit<AgentLogEntry, "id" | "at">): void {
  if (typeof window === "undefined") return;
  entries = [...entries.slice(-(MAX_ENTRIES - 1)), { ...entry, id: nextId, at: new Date().toISOString() }];
  nextId += 1;
  listeners.forEach((listener) => listener(entries));
}

export function getAgentLog(): AgentLogEntry[] {
  return entries;
}

export function subscribeAgentLog(listener: (current: AgentLogEntry[]) => void): () => void {
  listeners.add(listener);
  listener(entries);
  return () => {
    listeners.delete(listener);
  };
}
