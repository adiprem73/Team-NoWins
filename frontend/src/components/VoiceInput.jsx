import { useState, useRef } from "react";
import { Mic, MicOff, Square, Loader2 } from "lucide-react";

/**
 * VoiceInput — Records audio from the microphone and sends it to the backend
 * for mood analysis via Voxtral on Bedrock.
 *
 * This simulates how Alexa captures user speech:
 * 1. User clicks the mic button (or says wake word on real Alexa)
 * 2. Audio is recorded
 * 3. Sent to backend → Voxtral analyzes tone, pace, sentiment
 * 4. Returns mood + cognitive load
 */
export default function VoiceInput({ apiBase, onMoodResult, onError }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [duration, setDuration] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setAudioBlob(blob);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(100); // Collect chunks every 100ms
      setIsRecording(true);
      setDuration(0);
      setAudioBlob(null);

      // Timer
      timerRef.current = setInterval(() => {
        setDuration((d) => d + 1);
      }, 1000);
    } catch (err) {
      onError("Microphone access denied. Please allow mic permissions.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      clearInterval(timerRef.current);
    }
  };

  const analyzeAudio = async () => {
    if (!audioBlob) return;
    setIsAnalyzing(true);
    onError("");

    try {
      // Convert blob to base64
      const arrayBuffer = await audioBlob.arrayBuffer();
      const base64 = btoa(
        new Uint8Array(arrayBuffer).reduce(
          (data, byte) => data + String.fromCharCode(byte),
          ""
        )
      );

      const res = await fetch(`${apiBase}/mood/analyze/audio`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          audio_base64: base64,
          audio_format: "webm",
          user_id: "alexa-user",
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        onError(err.detail || "Audio analysis failed");
        setIsAnalyzing(false);
        return;
      }

      const data = await res.json();
      onMoodResult(data);
      setAudioBlob(null);
    } catch (err) {
      onError("Failed to analyze audio. Check backend connection.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const formatDuration = (sec) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
      <div className="flex items-center gap-2 mb-2">
        <Mic className="w-5 h-5 text-rose-400" />
        <h3 className="font-semibold text-white">Voice Input</h3>
        <span className="text-xs text-gray-500 ml-auto">
          Simulates Alexa listening
        </span>
      </div>
      <p className="text-gray-400 text-sm mb-5">
        Speak naturally — tone, pace, and emotion in your voice are analyzed to
        detect mood, just like Alexa would hear you in your room.
      </p>

      <div className="flex items-center gap-4">
        {/* Record button */}
        {!isRecording ? (
          <button
            onClick={startRecording}
            disabled={isAnalyzing}
            className="w-16 h-16 rounded-full bg-rose-600 hover:bg-rose-700 disabled:bg-gray-700 flex items-center justify-center transition-all hover:scale-105 active:scale-95 shadow-lg shadow-rose-600/20"
            aria-label="Start recording"
          >
            <Mic className="w-7 h-7 text-white" />
          </button>
        ) : (
          <button
            onClick={stopRecording}
            className="w-16 h-16 rounded-full bg-red-500 animate-pulse flex items-center justify-center transition-all shadow-lg shadow-red-500/30"
            aria-label="Stop recording"
          >
            <Square className="w-6 h-6 text-white" />
          </button>
        )}

        <div className="flex-1">
          {isRecording && (
            <div className="flex items-center gap-3">
              <div className="flex gap-1 items-end h-8">
                {[...Array(12)].map((_, i) => (
                  <div
                    key={i}
                    className="w-1 bg-rose-400 rounded-full animate-pulse"
                    style={{
                      height: `${Math.random() * 24 + 8}px`,
                      animationDelay: `${i * 0.1}s`,
                    }}
                  />
                ))}
              </div>
              <span className="text-rose-400 font-mono text-sm">
                {formatDuration(duration)}
              </span>
              <span className="text-xs text-gray-500">Recording...</span>
            </div>
          )}

          {!isRecording && audioBlob && (
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-300">
                🎙️ {formatDuration(duration)} recorded
              </span>
              <button
                onClick={analyzeAudio}
                disabled={isAnalyzing}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-900 text-white text-sm rounded-lg font-medium transition-colors flex items-center gap-2"
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  "Analyze Mood"
                )}
              </button>
              <button
                onClick={() => setAudioBlob(null)}
                className="text-xs text-gray-500 hover:text-gray-300"
              >
                Discard
              </button>
            </div>
          )}

          {!isRecording && !audioBlob && !isAnalyzing && (
            <p className="text-sm text-gray-500">
              Click the mic to start speaking — like talking to Alexa
            </p>
          )}
        </div>
      </div>

      {/* Also keep text fallback for demo */}
      <TextFallback apiBase={apiBase} onMoodResult={onMoodResult} onError={onError} />
    </div>
  );
}

/** Text fallback for when mic isn't available or for quick testing */
function TextFallback({ apiBase, onMoodResult, onError }) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);

  const analyze = async () => {
    if (!text.trim()) return;
    setLoading(true);
    onError("");
    try {
      const res = await fetch(`${apiBase}/mood/analyze/text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, user_id: "demo" }),
      });
      if (!res.ok) {
        const err = await res.json();
        onError(err.detail || "Analysis failed");
        setLoading(false);
        return;
      }
      const data = await res.json();
      onMoodResult({ ...data, _originalText: text });
      setText("");
    } catch (err) {
      onError("Network error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-5 pt-5 border-t border-gray-800">
      <p className="text-xs text-gray-500 mb-2">
        Or type what you'd say (text fallback):
      </p>
      <div className="flex gap-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && analyze()}
          placeholder="e.g. 'I'm so overwhelmed with work right now...'"
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
        />
        <button
          onClick={analyze}
          disabled={loading}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 text-white text-sm rounded-lg transition-colors"
        >
          {loading ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}
