/**
 * VoiceButton — browser-native speech-to-text via Web Speech API.
 *
 * Falls back gracefully: if the browser doesn't support SpeechRecognition
 * (Firefox, some mobile), the button renders disabled with a tooltip.
 *
 * On Chrome/Edge/Safari: tap to start recording, tap again to stop.
 * Transcript streams into the onTranscript callback as interim results
 * arrive, then fires onFinal with the complete text.
 *
 * No external API calls — this uses the browser's built-in speech engine.
 * For production, wire to Amazon Transcribe Streaming via WebSocket for
 * better accuracy and language support.
 */

import { useCallback, useRef, useState } from 'react';

// Web Speech API types (not in all TS libs)
interface SpeechRecognitionEvent {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent {
  error: string;
  message: string;
}

type SpeechRecognitionInstance = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onerror: ((e: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
};

function getSpeechRecognition(): (new () => SpeechRecognitionInstance) | null {
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null) as
    | (new () => SpeechRecognitionInstance)
    | null;
}

export interface VoiceButtonProps {
  /** Called with interim transcript text as the user speaks. */
  onTranscript: (text: string) => void;
  /** Called once when recognition ends with the final transcript. */
  onFinal?: (text: string) => void;
  /** Language code (default: en-US). */
  lang?: string;
  /** CSS class for the button. */
  className?: string;
  /** Inline style. */
  style?: React.CSSProperties;
}

export function VoiceButton({
  onTranscript,
  onFinal,
  lang = 'en-US',
  className,
  style,
}: VoiceButtonProps) {
  const [recording, setRecording] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const finalTextRef = useRef('');

  const SpeechRecognitionCtor = getSpeechRecognition();
  const supported = SpeechRecognitionCtor !== null;

  const toggle = useCallback(() => {
    if (!SpeechRecognitionCtor) return;

    if (recording && recognitionRef.current) {
      recognitionRef.current.stop();
      setRecording(false);
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = lang;
    recognitionRef.current = recognition;
    finalTextRef.current = '';

    recognition.onresult = (e: SpeechRecognitionEvent) => {
      let interim = '';
      let finalText = '';
      const results = e.results as unknown as Array<{ isFinal: boolean; 0?: { transcript: string } }>;
      for (let i = e.resultIndex; i < results.length; i++) {
        const result = results[i];
        if (!result?.[0]) continue;
        const transcript = result[0].transcript;
        if (result.isFinal) {
          finalText += transcript;
        } else {
          interim += transcript;
        }
      }
      if (finalText) {
        finalTextRef.current += finalText;
        onTranscript(finalTextRef.current);
      } else if (interim) {
        onTranscript(finalTextRef.current + interim);
      }
    };

    recognition.onerror = () => {
      setRecording(false);
    };

    recognition.onend = () => {
      setRecording(false);
      if (finalTextRef.current && onFinal) {
        onFinal(finalTextRef.current);
      }
    };

    recognition.start();
    setRecording(true);
  }, [SpeechRecognitionCtor, recording, lang, onTranscript, onFinal]);

  if (!supported) {
    return (
      <button
        type="button"
        className={className}
        style={{ ...style, opacity: 0.4, cursor: 'not-allowed' }}
        disabled
        title="Voice input not supported in this browser"
        aria-label="Voice input not supported"
      >
        🎙
      </button>
    );
  }

  return (
    <button
      type="button"
      className={className}
      style={{
        ...style,
        background: recording ? 'var(--v6-error, #dc3545)' : undefined,
        color: recording ? '#fff' : undefined,
        animation: recording ? 'v6-pulse 1.2s infinite' : undefined,
      }}
      onClick={toggle}
      title={recording ? 'Stop recording' : 'Start voice input'}
      aria-label={recording ? 'Stop voice recording' : 'Start voice recording'}
      aria-pressed={recording}
    >
      {recording ? '⏹' : '🎙'}
    </button>
  );
}
