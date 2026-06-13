import { useState, useEffect, useRef, useCallback } from "react";
import { MonitorSmartphone, Fingerprint, ArrowUpDown, Timer, Zap } from "lucide-react";

/**
 * BehaviorTracker — Monitors user interaction patterns.
 *
 * Key behaviors:
 * - Idle 15s+ → sends "idle" signal with high duration → backend scores as LOW cognitive load
 * - Aggressive scrolling → HIGH
 * - Rapid tapping → HIGH/OVERLOADED
 * - Normal activity → MODERATE
 *
 * Sends signals every 5 seconds. On significant state CHANGE, triggers LLM.
 */
export default function BehaviorTracker({ apiBase, onBehaviorResult, behaviorLog }) {
  const [tracking, setTracking] = useState(false);
  const [stats, setStats] = useState({
    scrollEvents: 0,
    tapEvents: 0,
    idleTime: 0,
    lastActivity: null,
  });

  const signalBufferRef = useRef([]);
  const flushIntervalRef = useRef(null);
  const lastScrollRef = useRef(0);
  const scrollCountRef = useRef(0);
  const tapTimesRef = useRef([]);
  const lastActivityRef = useRef(Date.now());
  const idleCheckRef = useRef(null);
  const lastCogLoadRef = useRef("moderate"); // Track previous state to detect changes

  const startTracking = () => {
    setTracking(true);
    setStats({ scrollEvents: 0, tapEvents: 0, idleTime: 0, lastActivity: Date.now() });
    signalBufferRef.current = [];
    lastActivityRef.current = Date.now();
    lastCogLoadRef.current = "moderate";

    // Flush signals to backend every 5 seconds
    flushIntervalRef.current = setInterval(flushSignals, 5000);

    // Check for idle every 3 seconds
    idleCheckRef.current = setInterval(checkIdle, 3000);
  };

  const stopTracking = () => {
    setTracking(false);
    clearInterval(flushIntervalRef.current);
    clearInterval(idleCheckRef.current);
    flushSignals();
  };

  // Check if user has been idle
  const checkIdle = () => {
    const now = Date.now();
    const idleDuration = now - lastActivityRef.current;

    if (idleDuration >= 15000) {
      // Idle for 15+ seconds — send a strong idle signal
      // Intensity scales with how long they've been idle
      const intensity = Math.min(1.0, idleDuration / 30000); // Max at 30s
      addSignal("idle", intensity, 0, idleDuration);
      setStats((s) => ({ ...s, idleTime: Math.round(idleDuration / 1000) }));
    }
  };

  const markActivity = () => {
    lastActivityRef.current = Date.now();
    setStats((s) => ({ ...s, lastActivity: Date.now(), idleTime: 0 }));
  };

  const addSignal = useCallback((type, intensity, frequency, durationMs) => {
    signalBufferRef.current.push({
      signal_type: type,
      intensity: Math.min(1, Math.max(0, intensity)),
      frequency: Math.max(0, frequency),
      duration_ms: Math.max(0, Math.round(durationMs)),
      timestamp: Date.now() / 1000,
    });
  }, []);

  // Send buffered signals to backend and detect state changes
  const flushSignals = async () => {
    const signals = [...signalBufferRef.current];
    signalBufferRef.current = [];

    // If no signals and idle, send an explicit idle signal
    if (signals.length === 0) {
      const idleDuration = Date.now() - lastActivityRef.current;
      if (idleDuration >= 10000) {
        signals.push({
          signal_type: "idle",
          intensity: Math.min(1.0, idleDuration / 30000),
          frequency: 0,
          duration_ms: idleDuration,
          timestamp: Date.now() / 1000,
        });
      } else {
        return; // Nothing to report
      }
    }

    try {
      const res = await fetch(`${apiBase}/behavior/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "alexa-user",
          device_id: "connected-device",
          signals,
        }),
      });
      if (res.ok) {
        const result = await res.json();
        const newLoad = result.cognitive_load;
        const prevLoad = lastCogLoadRef.current;

        // Detect significant state change
        const changed = newLoad !== prevLoad;
        lastCogLoadRef.current = newLoad;

        // Pass result up with a flag indicating if LLM should be triggered
        onBehaviorResult({
          ...result,
          _rawSignals: signals,
          _stateChanged: changed,
        });
      }
    } catch (err) {
      console.error("Behavior flush failed:", err);
    }
  };

  // Scroll handler
  useEffect(() => {
    if (!tracking) return;

    let lastScrollTime = 0;
    let scrollVelocities = [];

    const handleScroll = () => {
      const now = Date.now();
      const timeDelta = now - lastScrollRef.current;
      lastScrollRef.current = now;
      markActivity();

      scrollVelocities.push(timeDelta);

      if (now - lastScrollTime < 500) return;
      lastScrollTime = now;

      const avgDelta =
        scrollVelocities.reduce((a, b) => a + b, 0) / scrollVelocities.length;
      const eventCount = scrollVelocities.length;
      scrollVelocities = [];

      let speed = 0;
      if (avgDelta < 30 && eventCount > 8) speed = 0.9;
      else if (avgDelta < 50 && eventCount > 6) speed = 0.7;
      else if (avgDelta < 80 && eventCount > 4) speed = 0.4;
      else speed = 0.15;

      scrollCountRef.current += eventCount;
      addSignal("scroll", speed, Math.min(10, eventCount / 0.5), 500);
      setStats((s) => ({ ...s, scrollEvents: s.scrollEvents + eventCount }));
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    const main = document.querySelector("main");
    if (main) main.addEventListener("scroll", handleScroll, { passive: true });

    return () => {
      window.removeEventListener("scroll", handleScroll);
      if (main) main.removeEventListener("scroll", handleScroll);
    };
  }, [tracking, addSignal]);

  // Click/Tap handler
  useEffect(() => {
    if (!tracking) return;

    const handleClick = () => {
      const now = Date.now();
      markActivity();
      tapTimesRef.current.push(now);
      tapTimesRef.current = tapTimesRef.current.slice(-10);

      const recentTaps = tapTimesRef.current.filter((t) => now - t < 2000);
      const frequency = recentTaps.length / 2;
      const intensity = Math.min(1, frequency / 4);

      addSignal("tap", intensity, frequency, 100);
      setStats((s) => ({ ...s, tapEvents: s.tapEvents + 1 }));
    };

    document.addEventListener("click", handleClick);
    document.addEventListener("touchstart", handleClick, { passive: true });

    return () => {
      document.removeEventListener("click", handleClick);
      document.removeEventListener("touchstart", handleClick);
    };
  }, [tracking, addSignal]);

  // Touch move handler
  useEffect(() => {
    if (!tracking) return;

    let lastTouch = { x: 0, y: 0, time: 0 };

    const handleTouchMove = (e) => {
      const touch = e.touches[0];
      const now = Date.now();
      markActivity();
      const dx = touch.clientX - lastTouch.x;
      const dy = touch.clientY - lastTouch.y;
      const dt = now - lastTouch.time;

      if (dt > 0 && lastTouch.time > 0) {
        const speed = Math.sqrt(dx * dx + dy * dy) / dt;
        addSignal("swipe", Math.min(1, speed / 2), 1000 / Math.max(dt, 1), dt);
      }
      lastTouch = { x: touch.clientX, y: touch.clientY, time: now };
    };

    document.addEventListener("touchmove", handleTouchMove, { passive: true });
    return () => document.removeEventListener("touchmove", handleTouchMove);
  }, [tracking, addSignal]);

  return (
    <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <MonitorSmartphone className="w-5 h-5 text-emerald-400" />
          <h3 className="font-semibold text-white">Behavior Tracking</h3>
        </div>
        <button
          onClick={tracking ? stopTracking : startTracking}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            tracking
              ? "bg-red-600 hover:bg-red-700 text-white"
              : "bg-emerald-600 hover:bg-emerald-700 text-white"
          }`}
        >
          {tracking ? "Stop Tracking" : "Start Tracking"}
        </button>
      </div>
      <p className="text-gray-400 text-sm mb-5">
        Monitors scrolling, tapping, and idle patterns. 15s+ idle → sleep mode.
      </p>

      {tracking && (
        <div className="grid grid-cols-4 gap-3 mb-5">
          <StatCard icon={ArrowUpDown} label="Scrolls" value={stats.scrollEvents} color="text-blue-400" />
          <StatCard icon={Fingerprint} label="Taps" value={stats.tapEvents} color="text-rose-400" />
          <StatCard icon={Timer} label="Idle (s)" value={stats.idleTime} color="text-amber-400" />
          <StatCard icon={Zap} label="Signals" value={signalBufferRef.current.length} color="text-emerald-400" />
        </div>
      )}

      {behaviorLog.length > 0 && (
        <div className="border-t border-gray-800 pt-4">
          <p className="text-xs text-gray-500 mb-2">Recent Analysis:</p>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {behaviorLog.slice(0, 5).map((entry, i) => (
              <div key={i} className="flex items-center gap-3 text-xs bg-gray-800/50 rounded-lg px-3 py-2">
                <CogLoadBadge level={entry.cognitive_load} />
                <span className="text-gray-400">Agitation: {Math.round(entry.agitation_level * 100)}%</span>
                {entry.patterns_detected?.length > 0 && (
                  <span className="text-gray-500">[{entry.patterns_detected.join(", ")}]</span>
                )}
                <span className="text-gray-600 ml-auto">{entry.timestamp?.toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!tracking && behaviorLog.length === 0 && (
        <div className="text-center py-4 text-gray-600 text-sm">
          Start tracking to monitor interaction patterns
        </div>
      )}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-gray-800/50 rounded-lg p-3 text-center">
      <Icon className={`w-4 h-4 mx-auto mb-1 ${color}`} />
      <p className="text-lg font-bold text-white">{value}</p>
      <p className="text-xs text-gray-500">{label}</p>
    </div>
  );
}

function CogLoadBadge({ level }) {
  const config = {
    low: { bg: "bg-green-900/30", text: "text-green-400" },
    moderate: { bg: "bg-yellow-900/30", text: "text-yellow-400" },
    high: { bg: "bg-orange-900/30", text: "text-orange-400" },
    overloaded: { bg: "bg-red-900/30", text: "text-red-400" },
  };
  const c = config[level] || config.moderate;
  return (
    <span className={`px-2 py-0.5 rounded ${c.bg} ${c.text} capitalize`}>
      {level}
    </span>
  );
}
