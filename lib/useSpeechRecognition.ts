"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { showToast } from "@/lib/toast";
import { transcribeAudio } from "@/lib/api";

type SpeechRecognitionEventLike = {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
  resultIndex: number;
};

type SpeechRecognitionErrorLike = { error: string };

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: SpeechRecognitionErrorLike) => void) | null;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

const PERMISSION_ERRORS = new Set(["not-allowed", "service-not-allowed"]);

export function speechRecognitionSupported(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as Window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

/** Whether the server exposes a real STT provider (set in .env — see NEXT_PUBLIC_SERVER_STT_ENABLED). */
export function serverSttEnabled(): boolean {
  return process.env.NEXT_PUBLIC_SERVER_STT_ENABLED === "true";
}

export function mediaRecorderSupported(): boolean {
  return typeof window !== "undefined" && typeof window.MediaRecorder !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);
}

/**
 * Native Web Speech API hook — the default STT path while no server
 * STT_PROVIDER is configured. Streams interim transcripts and reports the
 * final phrase through onFinal.
 */
export function useSpeechRecognition({
  onFinal,
  lang = "en-US",
}: {
  onFinal: (text: string) => void;
  lang?: string;
}) {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const onFinalRef = useRef(onFinal);
  onFinalRef.current = onFinal;

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
  }, []);

  // MediaRecorder -> /voice/transcribe fallback, used only when the browser has
  // no Web Speech support but the server exposes a real STT provider.
  const startServerRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: BlobPart[] = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (event) => { if (event.data.size > 0) chunks.push(event.data); };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        mediaRecorderRef.current = null;
        setListening(false);
        const audioBlob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        if (audioBlob.size === 0) return;
        void transcribeAudio(audioBlob)
          .then((result) => { if (result.transcript.trim()) onFinalRef.current(result.transcript.trim()); })
          .catch(() => showToast("Could not transcribe that recording. Try again.", "error"));
      };
      mediaRecorderRef.current = recorder;
      setListening(true);
      recorder.start();
    } catch {
      setListening(false);
      showToast("Microphone permission denied — allow mic access in your browser and try again.", "error");
    }
  }, []);

  const start = useCallback(() => {
    if (recognitionRef.current || mediaRecorderRef.current) return;
    const w = window as Window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
    const SpeechRecognition = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      if (serverSttEnabled() && mediaRecorderSupported()) {
        void startServerRecording();
      } else {
        showToast("Voice input needs Chrome or Edge — no STT provider is configured on the server yet.", "error");
      }
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = lang;
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      let live = "";
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = result[0]?.transcript ?? "";
        if ((result as unknown as { isFinal?: boolean }).isFinal) finalText += text;
        else live += text;
      }
      setInterim(live);
      if (finalText.trim()) {
        setInterim("");
        onFinalRef.current(finalText.trim());
      }
    };
    recognition.onerror = (event) => {
      setListening(false);
      setInterim("");
      recognitionRef.current = null;
      if (PERMISSION_ERRORS.has(event.error)) {
        showToast("Microphone permission denied — allow mic access in your browser and try again.", "error");
      } else if (event.error !== "aborted" && event.error !== "no-speech") {
        showToast("Could not capture voice input. Check your microphone and try again.", "error");
      } else if (event.error === "no-speech") {
        showToast("No speech detected — tap the mic and speak.", "info");
      }
    };
    recognition.onend = () => {
      setListening(false);
      setInterim("");
      recognitionRef.current = null;
    };
    recognitionRef.current = recognition;
    setListening(true);
    try {
      recognition.start();
    } catch {
      setListening(false);
      recognitionRef.current = null;
      showToast("Microphone could not start — check permissions and try again.", "error");
    }
  }, [lang, startServerRecording]);

  useEffect(() => () => {
    recognitionRef.current?.abort();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") mediaRecorderRef.current.stop();
  }, []);

  return { listening, interim, start, stop, supported: speechRecognitionSupported() || (serverSttEnabled() && mediaRecorderSupported()) };
}
