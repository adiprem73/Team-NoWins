import { useEffect, useRef, useState } from "react";

// Pick a pleasant English voice for the "Alexa" persona, preferring a female
// voice when one is available. Voices load asynchronously in some browsers.
function pickVoice() {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  if (!voices.length) return null;
  const en = voices.filter((v) => /^en(-|_|$)/i.test(v.lang));
  const pool = en.length ? en : voices;
  const preferred = pool.find((v) =>
    /samantha|female|zira|google us english|aria|jenny|alexa/i.test(v.name),
  );
  return preferred || pool[0];
}

// Alexa-style voice notification popup. Appears bottom-right when the engine
// produces a spoken-language response for the current context, READS IT ALOUD
// via the browser Web Speech API, auto-dismisses after a delay (pause on hover
// / when expanded); click ✕ to close immediately.
//
// Props:
//   notification: { id, text, explanation, llmPowered, tone } | null
//   onClose: () => void
export default function AlexaNotification({ notification, onClose }) {
  const [visible, setVisible] = useState(false);
  const [hover, setHover] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  // Voice on/off, remembered across sessions.
  const [muted, setMuted] = useState(() => {
    try {
      return localStorage.getItem("alexa_tts_muted") === "1";
    } catch {
      return false;
    }
  });
  const lastSpokenId = useRef(null);

  const ttsSupported =
    typeof window !== "undefined" && "speechSynthesis" in window;

  // Persist mute preference.
  useEffect(() => {
    try {
      localStorage.setItem("alexa_tts_muted", muted ? "1" : "0");
    } catch {
      /* ignore storage failures */
    }
  }, [muted]);

  // Speak the message aloud whenever a NEW notification arrives (once per id).
  useEffect(() => {
    if (!notification || !ttsSupported) return;
    if (muted) return;
    if (lastSpokenId.current === notification.id) return;
    lastSpokenId.current = notification.id;

    const synth = window.speechSynthesis;
    synth.cancel(); // stop anything still speaking
    const utter = new SpeechSynthesisUtterance(notification.text);
    utter.rate = 1.02;
    utter.pitch = 1.0;
    const voice = pickVoice();
    if (voice) utter.voice = voice;
    utter.onstart = () => setSpeaking(true);
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    // Some browsers need a tick after cancel() before speak() takes effect.
    const t = setTimeout(() => synth.speak(utter), 60);
    return () => clearTimeout(t);
  }, [notification, muted, ttsSupported]);

  // Stop any speech when the popup is dismissed/unmounted.
  useEffect(() => {
    if (!ttsSupported) return;
    if (!visible) window.speechSynthesis.cancel();
    return () => window.speechSynthesis.cancel();
  }, [visible, ttsSupported]);

  const replay = () => {
    if (!ttsSupported || !notification) return;
    const synth = window.speechSynthesis;
    synth.cancel();
    const utter = new SpeechSynthesisUtterance(notification.text);
    utter.rate = 1.02;
    const voice = pickVoice();
    if (voice) utter.voice = voice;
    utter.onstart = () => setSpeaking(true);
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    synth.speak(utter);
  };

  const toggleMute = () => {
    setMuted((m) => {
      const next = !m;
      if (next && ttsSupported) window.speechSynthesis.cancel();
      return next;
    });
  };

  // Slide in when a new notification arrives (and collapse any prior detail).
  useEffect(() => {
    if (!notification) return;
    setVisible(true);
    setExpanded(false);
  }, [notification]);

  // Auto-dismiss timer (paused while hovered OR while the detail is expanded OR
  // while actively speaking, so it never vanishes mid-sentence).
  useEffect(() => {
    if (!notification || hover || expanded || speaking) return;
    const ms = notification.tone === "alert" ? 9000 : 6000;
    const t = setTimeout(() => setVisible(false), ms);
    return () => clearTimeout(t);
  }, [notification, hover, expanded, speaking]);

  // After the slide-out transition, tell the parent to clear it.
  useEffect(() => {
    if (visible || !notification) return;
    const t = setTimeout(() => onClose?.(), 320);
    return () => clearTimeout(t);
  }, [visible, notification, onClose]);

  if (!notification) return null;

  const alert = notification.tone === "alert";

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className={[
        "fixed bottom-5 right-5 z-50 w-[360px] max-w-[calc(100vw-2.5rem)]",
        "transition-all duration-300 ease-out",
        visible ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0",
      ].join(" ")}
      role="status"
      aria-live="polite"
    >
      <div
        className={[
          "relative overflow-hidden rounded-2xl border bg-slate-900/95 p-4 shadow-2xl backdrop-blur",
          alert ? "border-red-500/50" : "border-sky-500/40",
        ].join(" ")}
      >
        {/* Glow accent bar */}
        <span
          className={[
            "absolute inset-x-0 top-0 h-0.5",
            alert
              ? "bg-gradient-to-r from-red-500 via-orange-400 to-red-500"
              : "bg-gradient-to-r from-sky-400 via-cyan-300 to-indigo-400",
          ].join(" ")}
        />

        <div className="flex items-start gap-3">
          {/* Alexa ring / speaking pulse */}
          <div className="relative mt-0.5 shrink-0">
            <span
              className={[
                "block h-10 w-10 rounded-full ring-2",
                alert ? "ring-red-400/70" : "ring-sky-400/70",
              ].join(" ")}
              style={{
                background: alert
                  ? "radial-gradient(circle at 50% 50%, #fca5a5 0%, #0ea5e9 0%, #0f172a 70%)"
                  : "radial-gradient(circle at 50% 50%, #67e8f9 0%, #0ea5e9 45%, #0f172a 75%)",
              }}
            />
            {/* speaking dots */}
            <span className="alexa-ping absolute inset-0 rounded-full" />
          </div>

          <div className="min-w-0 flex-1">
            <div className="mb-0.5 flex items-center gap-2">
              <span className="text-xs font-bold tracking-wide text-slate-200">
                Alexa
              </span>
              <span
                className={[
                  "rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide ring-1",
                  notification.llmPowered
                    ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/40"
                    : "bg-slate-700/50 text-slate-400 ring-slate-600/50",
                ].join(" ")}
                title={
                  notification.llmPowered
                    ? "Phrased live by the Groq LLM"
                    : "Deterministic fallback (set GROQ_API_KEY for LLM phrasing)"
                }
              >
                {notification.llmPowered ? "✦ LLM" : "fallback"}
              </span>

              {speaking && !muted && (
                <span className="flex items-center gap-0.5" title="Speaking…">
                  <span className="tts-bar h-2 w-0.5 rounded bg-sky-400" />
                  <span className="tts-bar tts-bar-2 h-3 w-0.5 rounded bg-sky-400" />
                  <span className="tts-bar tts-bar-3 h-2 w-0.5 rounded bg-sky-400" />
                </span>
              )}

              {ttsSupported && (
                <div className="ml-auto flex items-center gap-1">
                  {!muted && (
                    <button
                      onClick={replay}
                      title="Replay voice"
                      className="rounded p-0.5 text-slate-500 transition hover:bg-slate-800 hover:text-sky-300"
                      aria-label="Replay voice"
                    >
                      ⟲
                    </button>
                  )}
                  <button
                    onClick={toggleMute}
                    title={muted ? "Unmute voice" : "Mute voice"}
                    className={[
                      "rounded p-0.5 transition hover:bg-slate-800",
                      muted ? "text-slate-500 hover:text-slate-300" : "text-sky-300",
                    ].join(" ")}
                    aria-label={muted ? "Unmute voice" : "Mute voice"}
                  >
                    {muted ? "🔇" : "🔊"}
                  </button>
                </div>
              )}
            </div>
            <p className="text-sm leading-relaxed text-slate-100">
              {notification.text}
            </p>

            {/* See more — expandable reasoning from the LLM */}
            {notification.explanation && (
              <>
                <button
                  onClick={() => setExpanded((v) => !v)}
                  className={[
                    "mt-2 inline-flex items-center gap-1 text-[11px] font-semibold transition",
                    alert
                      ? "text-red-300 hover:text-red-200"
                      : "text-sky-300 hover:text-sky-200",
                  ].join(" ")}
                  aria-expanded={expanded}
                >
                  {expanded ? "Hide details" : "See more"}
                  <span
                    className={[
                      "transition-transform",
                      expanded ? "rotate-180" : "",
                    ].join(" ")}
                  >
                    ▾
                  </span>
                </button>

                <div
                  className={[
                    "grid transition-all duration-300 ease-out",
                    expanded
                      ? "mt-2 grid-rows-[1fr] opacity-100"
                      : "grid-rows-[0fr] opacity-0",
                  ].join(" ")}
                >
                  <div className="overflow-hidden">
                    <div className="rounded-lg border border-slate-700/60 bg-slate-950/60 p-2.5">
                      <p className="mb-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                        <span>🧠</span> Why I think this
                      </p>
                      <p className="text-[12px] leading-relaxed text-slate-300">
                        {notification.explanation}
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>

          <button
            onClick={() => setVisible(false)}
            className="shrink-0 rounded-md p-1 text-slate-500 transition hover:bg-slate-800 hover:text-slate-200"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  );
}
