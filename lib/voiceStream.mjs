export function sendVoiceTranscript(socket, pending, text, final) {
  const message = JSON.stringify({ type: "transcript", text, final });
  if (socket?.readyState === 1) socket.send(message);
  else if (socket?.readyState === 0) pending.push(message);
}

export function flushVoiceEvents(socket, pending) {
  if (socket?.readyState !== 1) return;
  for (const event of pending.splice(0)) socket.send(event);
}

export function interruptVoiceOutput(socket, speechSynthesis) {
  speechSynthesis?.cancel();
  if (socket?.readyState === 1) socket.send(JSON.stringify({ type: "interrupt" }));
}

export function parseVoiceEvent(raw) {
  try {
    const event = JSON.parse(raw);
    return event && typeof event === "object" && typeof event.type === "string" ? event : null;
  } catch {
    return null;
  }
}
