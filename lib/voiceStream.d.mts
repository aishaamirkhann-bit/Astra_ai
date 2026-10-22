export function sendVoiceTranscript(socket: WebSocket | null, pending: string[], text: string, final: boolean): void;
export function flushVoiceEvents(socket: WebSocket | null, pending: string[]): void;
export function interruptVoiceOutput(socket: WebSocket | null, speechSynthesis: Pick<SpeechSynthesis, "cancel"> | undefined): void;
export function parseVoiceEvent(raw: string): ({ type: string; [key: string]: unknown } | null);
