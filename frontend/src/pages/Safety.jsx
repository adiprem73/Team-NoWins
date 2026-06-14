import { useCallback, useEffect, useMemo, useState } from "react";
import { safetyApi } from "../safetyApi.js";
import AlexaNotification from "../components/patterns/AlexaNotification.jsx";

// ── Static layout for the elderly home (E001). Rooms on a 3x3 grid; each
//    device id maps to a room + icon so the floor plan can light up risks. ──
const ROOMS = {
  bedroom: { name: "Bedroom", col: "1 / 2", row: "1 / 2" },
  pooja_room: { name: "Pooja Room", col: "2 / 3", row: "1 / 2" },
  balcony: { name: "Balcony", col: "3 / 4", row: "1 / 2" },
  living_room: { name: "Living Room", col: "1 / 3", row: "2 / 3" },
  kitchen: { name: "Kitchen", col: "3 / 4", row: "2 / 3" },
  entrance: { name: "Entrance", col: "1 / 2", row: "3 / 4" },
  utility: { name: "Utility", col: "2 / 4", row: "3 / 4" },
};

const DEVICE_META = {
  grandpa_activity: { room: "bedroom", icon: "🚶", label: "Grandpa activity" },
  grandma_activity: { room: "bedroom", icon: "🚶", label: "Grandma activity" },
  grandpa_medicine: { room: "bedroom", icon: "💊", label: "Grandpa medicine" },
  grandma_medicine: { room: "bedroom", icon: "💊", label: "Grandma medicine" },
  bedroom_window: { room: "bedroom", icon: "🪟", label: "Bedroom window" },
  grandpa_wearable: { room: "living_room", icon: "⌚", label: "Wearable" },
  pooja_lamp: { room: "pooja_room", icon: "🪔", label: "Pooja lamp" },
  temple_bell: { room: "pooja_room", icon: "🔔", label: "Temple bell" },
  bhajan_speaker: { room: "pooja_room", icon: "🔊", label: "Bhajan" },
  kitchen_activity: { room: "kitchen", icon: "🍳", label: "Kitchen activity" },
  kitchen_gas_stove: { room: "kitchen", icon: "🔥", label: "Gas stove" },
  living_activity: { room: "living_room", icon: "🛋️", label: "Living activity" },
  living_room_light: { room: "living_room", icon: "💡", label: "Living light" },
  main_door: { room: "entrance", icon: "🚪", label: "Main door" },
  water_motor: { room: "utility", icon: "🛢️", label: "Water motor" },
};

const STATUS_META = {
  safe: { label: "Safe", color: "#22c55e", bg: "bg-emerald-500/15", ring: "ring-emerald-500/50", text: "text-emerald-300", emoji: "🟢" },
  inactive: { label: "Inactive", color: "#eab308", bg: "bg-yellow-500/15", ring: "ring-yellow-500/50", text: "text-yellow-300", emoji: "🟡" },
  needs_attention: { label: "Needs Attention", color: "#f97316", bg: "bg-orange-500/15", ring: "ring-orange-500/50", text: "text-orange-300", emoji: "🟠" },
  emergency: { label: "Emergency", color: "#ef4444", bg: "bg-red-500/15", ring: "ring-red-500/60", text: "text-red-300", emoji: "🔴" },
};

const SEVERITY_COLOR = {
  low: { dot: "bg-emerald-400", text: "text-emerald-300", ring: "border-emerald-500/40" },
  medium: { dot: "bg-yellow-400", text: "text-yellow-300", ring: "border-yellow-500/40" },
  high: { dot: "bg-orange-400", text: "text-orange-300", ring: "border-orange-500/40" },
  critical: { dot: "bg-red-500", text: "text-red-300", ring: "border-red-500/50" },
};

const SCENARIOS = [
  { key: "sos", label: "SOS pressed", emoji: "🆘" },
  { key: "health", label: "Abnormal heart rate", emoji: "❤️" },
  { key: "gas", label: "Gas left on", emoji: "🔥" },
  { key: "window_night", label: "Window open at night", emoji: "🪟" },
  { key: "inactivity", label: "No activity (4h+)", emoji: "🟡" },
];

// Who is home — the vulnerability lens. Same home + same concern, but the
// severity is escalated differently depending on who is at risk.
const HOUSEHOLD_PRESETS = [
  { key: "elderly", label: "Elderly couple", emoji: "👴👵" },
  { key: "child_alone", label: "Child alone", emoji: "🧒" },
  { key: "pregnant_alone", label: "Expecting mother", emoji: "🤰" },
  { key: "unwell_alone", label: "Recovering / unwell", emoji: "🤒" },
  { key: "mixed_support", label: "Elderly + adult", emoji: "🧑‍🦱👵" },
];

// Per-vulnerability visual identity (badge + factor hint).
const VULN_META = {
  elderly: { label: "Elderly", emoji: "👴", cls: "bg-rose-500/15 text-rose-300 ring-rose-500/40", factor: "×2.0" },
  child: { label: "Child", emoji: "🧒", cls: "bg-amber-500/15 text-amber-300 ring-amber-500/40", factor: "×1.7" },
  pregnant: { label: "Expecting", emoji: "🤰", cls: "bg-pink-500/15 text-pink-300 ring-pink-500/40", factor: "×1.8" },
  unwell: { label: "Unwell", emoji: "🤒", cls: "bg-orange-500/15 text-orange-300 ring-orange-500/40", factor: "×1.8" },
  normal: { label: "Adult", emoji: "🧑", cls: "bg-slate-600/30 text-slate-300 ring-slate-500/40", factor: "×1.0" },
};

function nowHHMM() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function timeAgo(iso) {
  if (!iso) return "—";
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `${mins} min ago`;
  const h = (mins / 60).toFixed(1);
  return `${h} h ago`;
}

export default function Safety() {
  const HID = "E001";
  const [simTime, setSimTime] = useState("");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState(true);
  // Multiple safety threats can be simulated at once (like the patterns demo).
  const [selectedThreats, setSelectedThreats] = useState(() => new Set());
  const [household, setHousehold] = useState("elderly");
  const [alexaQueue, setAlexaQueue] = useState([]);
  const [toast, setToast] = useState(null);

  const flash = useCallback((msg, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 2600);
  }, []);

  const speak = useCallback(async (ctx) => {
    if (!ctx) return;
    try {
      const { narrations } = await safetyApi.narrateEach(ctx);
      const items = (narrations || [])
        .filter((n) => n && n.alexa_response)
        .map((n, i) => ({
          id: `${Date.now()}-${i}-${n.device || "all"}`,
          text: n.alexa_response,
          explanation: n.explanation,
          llmPowered: n.llm_powered,
          tone:
            n.severity === "high" || n.severity === "critical" || n.severity === "medium"
              ? "alert"
              : "calm",
        }));
      setAlexaQueue(items);
    } catch {
      /* narration optional */
    }
  }, []);

  const load = useCallback(
    async (at = simTime, { withVoice = true } = {}) => {
      setBusy(true);
      try {
        const d = await safetyApi.getSafety(HID, at || undefined);
        setData(d);
        setConnected(true);
        // Only narrate (and pop notifications) when asked — on first arrival we
        // stay calm and silent until the user runs a simulation or refresh.
        if (withVoice) speak(d.context);
      } catch (e) {
        setConnected(false);
        flash(`Cannot reach Safety API on :8006 — is it running? (${e.message})`, false);
      } finally {
        setBusy(false);
      }
    },
    [simTime, speak, flash],
  );

  // First arrival: load the live picture but stay quiet — no notifications until
  // the user simulates a threat or hits Refresh.
  useEffect(() => {
    load(simTime, { withVoice: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Seed the home with whatever threats are currently selected (may be many at
  // once). With none selected this seeds a normal, safe day.
  const runThreats = useCallback(
    async (threats) => {
      setBusy(true);
      try {
        const keys = threats.size ? [...threats].join(",") : "normal";
        const res = await safetyApi.seed(HID, keys);
        // Seeding rewrites the default (elderly) profiles — re-apply whoever the
        // user currently has selected so "who's home" survives a scenario change.
        if (household !== "elderly") {
          await safetyApi.setHousehold(HID, household);
        }
        // Injected threats are timestamped at "now", so evaluate at the real
        // clock (clear any simulated time) — this guarantees every selected
        // threat fires together, including a window/door opened "moments ago".
        setSimTime("");
        const label = threats.size
          ? `Simulating ${threats.size} threat${threats.size > 1 ? "s" : ""}`
          : "Reset to a normal, safe day";
        flash(`${label} · ${res.events_stored} events`);
        await load("");
      } catch (e) {
        flash(`Simulation failed: ${e.message}`, false);
      } finally {
        setBusy(false);
      }
    },
    [load, flash, household],
  );

  // Toggle a threat in/out of the selection (does NOT seed until "Simulate").
  const toggleThreat = useCallback((key) => {
    setSelectedThreats((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const clearThreats = useCallback(async () => {
    setSelectedThreats(new Set());
    await runThreats(new Set());
  }, [runThreats]);

  // Switch WHO is home (vulnerability lens) without re-seeding the routine.
  const handleHousehold = useCallback(
    async (preset) => {
      setBusy(true);
      setHousehold(preset);
      try {
        const res = await safetyApi.setHousehold(HID, preset);
        const who = (res.members || [])
          .map((m) => `${m.name} (${m.vulnerability})`)
          .join(", ");
        flash(`Now home: ${who}`);
        await load(simTime);
      } catch (e) {
        flash(`Could not switch household: ${e.message}`, false);
      } finally {
        setBusy(false);
      }
    },
    [load, simTime, flash],
  );

  const safety = data?.safety;
  const context = data?.context;
  const profiles = data?.profiles || [];
  const anomalies = context?.anomalies || [];
  const status = STATUS_META[safety?.status] || STATUS_META.safe;

  // Map room -> worst severity among its devices' anomalies.
  const roomRisk = useMemo(() => {
    const sev = { low: 1, medium: 2, high: 3, critical: 4 };
    const m = {};
    anomalies.forEach((a) => {
      const meta = DEVICE_META[a.device];
      const room = meta?.room;
      if (!room) return;
      if (!m[room] || sev[a.severity] > sev[m[room]]) m[room] = a.severity;
    });
    return m;
  }, [anomalies]);

  const activeSet = useMemo(
    () => new Set(data?.state?.active_devices || []),
    [data],
  );

  // Last activity per person from the timeline.
  const lastActivity = useMemo(() => {
    const m = {};
    (data?.timeline || []).forEach((e) => {
      const who = e.triggered_by;
      if (who && !m[who]) m[who] = e;
    });
    return m;
  }, [data]);

  return (
    <div className="mx-auto flex min-h-full max-w-[1400px] flex-col gap-4">
      {/* Header */}
      <header className="flex flex-col gap-3 rounded-2xl border border-slate-700/60 bg-slate-900/60 px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-rose-500 to-red-600 text-lg shadow-lg">
              🛡️
            </span>
            <div className="leading-tight">
              <h1 className="text-sm font-bold text-slate-100">Adaptive Safety Intelligence</h1>
              <p className="text-[10px] text-slate-400">
                Protects whoever is vulnerable at home · acts on its own
              </p>
            </div>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <label className="flex items-center gap-1.5 text-xs text-slate-400">
              🕒
              <input
                type="time"
                value={simTime}
                onChange={(e) => setSimTime(e.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-800 px-2 py-1.5 text-xs text-slate-100 outline-none focus:border-rose-500"
              />
            </label>
            <button
              onClick={() => setSimTime(nowHHMM())}
              className="rounded-lg border border-slate-700 px-2 py-1.5 text-[10px] text-slate-400 hover:text-slate-200"
              title="Set clock to now"
            >
              now
            </button>
            <button
              onClick={() => load(simTime)}
              disabled={busy}
              className="rounded-lg border border-rose-500/50 bg-rose-500/15 px-3 py-1.5 text-xs font-bold text-rose-200 transition hover:bg-rose-500/25 disabled:opacity-50"
            >
              {busy ? "… Checking" : "▶ Refresh"}
            </button>
            <span
              className={[
                "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium",
                connected ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300",
              ].join(" ")}
            >
              <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "bg-red-400"}`} />
              {connected ? "Safety API :8006" : "API offline"}
            </span>
          </div>
        </div>

        {/* Who is home (vulnerability lens) */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Who's home
          </span>
          {HOUSEHOLD_PRESETS.map((h) => (
            <button
              key={h.key}
              onClick={() => handleHousehold(h.key)}
              disabled={busy}
              className={[
                "rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold transition disabled:opacity-50",
                household === h.key
                  ? "border-sky-400/60 bg-sky-500/20 text-sky-100"
                  : "border-slate-700 bg-slate-800/60 text-slate-300 hover:border-slate-500",
              ].join(" ")}
              title={`Set who is home: ${h.label}`}
            >
              {h.emoji} {h.label}
            </button>
          ))}
        </div>

        {/* What's happening today (safety scenario) */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Simulate threats
          </span>
          {SCENARIOS.map((s) => {
            const on = selectedThreats.has(s.key);
            return (
              <button
                key={s.key}
                onClick={() => toggleThreat(s.key)}
                disabled={busy}
                className={[
                  "rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold transition disabled:opacity-50",
                  on
                    ? "border-rose-400/70 bg-rose-500/25 text-rose-100 ring-1 ring-rose-500/40"
                    : "border-slate-700 bg-slate-800/60 text-slate-300 hover:border-slate-500",
                ].join(" ")}
                title={`Toggle threat: ${s.label}`}
              >
                {on ? "✓ " : ""}{s.emoji} {s.label}
              </button>
            );
          })}
          <button
            onClick={() => runThreats(selectedThreats)}
            disabled={busy}
            className={[
              "rounded-lg px-3 py-1.5 text-[11px] font-bold transition disabled:opacity-50",
              selectedThreats.size
                ? "animate-pulse border border-rose-400 bg-rose-500/30 text-rose-50 shadow-lg shadow-rose-500/20"
                : "border border-slate-600 bg-slate-800/60 text-slate-400",
            ].join(" ")}
            title="Inject the selected threats and trigger Alexa's response"
          >
            {busy
              ? "… Simulating"
              : selectedThreats.size
                ? `▶ Simulate ${selectedThreats.size} threat${selectedThreats.size > 1 ? "s" : ""}`
                : "▶ Simulate"}
          </button>
          <button
            onClick={clearThreats}
            disabled={busy}
            className="rounded-lg border border-emerald-600/50 bg-emerald-500/10 px-2.5 py-1.5 text-[11px] font-semibold text-emerald-300 transition hover:bg-emerald-500/20 disabled:opacity-50"
            title="Clear all threats — back to a normal, safe day"
          >
            🟢 All clear
          </button>
        </div>
      </header>

      {/* Status banner */}
      <section
        className={[
          "flex flex-wrap items-center gap-4 rounded-2xl border bg-slate-900/60 p-4 ring-1",
          status.ring,
        ].join(" ")}
      >
        <div className={["grid h-16 w-16 place-items-center rounded-2xl text-3xl", status.bg].join(" ")}>
          {status.emoji}
        </div>
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-wide text-slate-400">Home status</p>
          <p className={["text-2xl font-extrabold", status.text].join(" ")}>{status.label}</p>
          <p className="mt-0.5 max-w-2xl text-xs text-slate-400">{safety?.rationale}</p>
        </div>

        {/* Safety score gauge */}
        <div className="ml-auto flex items-center gap-4">
          {safety?.vulnerable_alone && (
            <span className="rounded-full bg-rose-500/15 px-3 py-1.5 text-[11px] font-semibold text-rose-300 ring-1 ring-rose-500/40">
              ⚠ Vulnerable person home alone ×{safety?.vulnerability_factor}
            </span>
          )}
          <div className="text-center">
            <div
              className="grid h-20 w-20 place-items-center rounded-full"
              style={{
                background: `conic-gradient(${status.color} ${(safety?.safety_score ?? 100) * 3.6}deg, #1e293b 0deg)`,
              }}
            >
              <div className="grid h-16 w-16 place-items-center rounded-full bg-slate-950">
                <span className="text-xl font-bold text-slate-100">
                  {Math.round(safety?.safety_score ?? 100)}
                </span>
              </div>
            </div>
            <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-500">Safety score</p>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_360px]">
        {/* Left: floor plan + vulnerability list */}
        <main className="flex flex-col gap-4">
          {/* Floor plan */}
          <div className="rounded-3xl border border-slate-700/50 bg-slate-950/40 p-4">
            <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
              Home Layout · live
            </p>
            <div
              className="grid gap-3"
              style={{ gridTemplateColumns: "repeat(3, 1fr)", gridTemplateRows: "repeat(3, minmax(120px,1fr))" }}
            >
              {Object.entries(ROOMS).map(([key, room]) => {
                const risk = roomRisk[key];
                const sev = risk ? SEVERITY_COLOR[risk] : null;
                const devices = Object.entries(DEVICE_META).filter(([, m]) => m.room === key);
                return (
                  <div
                    key={key}
                    style={{ gridColumn: room.col, gridRow: room.row }}
                    className={[
                      "rounded-2xl border p-3 transition-all",
                      sev
                        ? `${sev.ring} bg-slate-900/80 ${risk === "critical" ? "anomaly-pulse" : ""}`
                        : "border-slate-700/60 bg-slate-900/40",
                    ].join(" ")}
                  >
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-200">{room.name}</span>
                      {risk && (
                        <span className={["text-[9px] font-bold uppercase", sev.text].join(" ")}>
                          ⚠ {risk}
                        </span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {devices.map(([id, m]) => {
                        const on = activeSet.has(id);
                        const flagged = anomalies.some((a) => a.device === id);
                        return (
                          <span
                            key={id}
                            title={`${m.label}${on ? " · active" : ""}${flagged ? " · ⚠" : ""}`}
                            className={[
                              "grid h-7 w-7 place-items-center rounded-lg text-sm transition",
                              flagged
                                ? "bg-red-500/20 ring-1 ring-red-500/50"
                                : on
                                  ? "bg-sky-500/15 ring-1 ring-sky-400/40"
                                  : "bg-slate-800/60",
                            ].join(" ")}
                          >
                            {m.icon}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Vulnerability monitoring */}
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Vulnerability Monitoring
            </p>
            {anomalies.length === 0 ? (
              <p className="rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
                ✓ No safety concerns — routines, home-safety and health all look normal.
              </p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {anomalies
                  .slice()
                  .sort((a, b) => ({ critical: 0, high: 1, medium: 2, low: 3 }[a.severity] - { critical: 0, high: 1, medium: 2, low: 3 }[b.severity]))
                  .map((a, i) => {
                    const sev = SEVERITY_COLOR[a.severity] || SEVERITY_COLOR.medium;
                    return (
                      <li
                        key={i}
                        className={["flex items-start gap-2 rounded-lg border bg-slate-950/40 px-3 py-2", sev.ring].join(" ")}
                      >
                        <span className={["mt-1.5 h-2 w-2 shrink-0 rounded-full", sev.dot].join(" ")} />
                        <div className="min-w-0">
                          <p className="text-sm text-slate-100">{a.detail}</p>
                          <p className="text-[10px] uppercase tracking-wide text-slate-500">
                            <span className={sev.text}>{a.severity}</span>
                            {a.base_severity && a.base_severity !== a.severity && (
                              <span className="text-slate-600"> · escalated from {a.base_severity} (×{a.vulnerability_factor})</span>
                            )}
                            {" · "}
                            {a.type}
                          </p>
                        </div>
                      </li>
                    );
                  })}
              </ul>
            )}
          </div>
        </main>

        {/* Right: who's home + timeline */}
        <aside className="flex flex-col gap-4">
          {/* Members at home panel */}
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Who's Home
            </p>
            <div className="flex flex-col gap-2">
              {profiles.map((p) => {
                const la = lastActivity[p.person_id];
                const vm = VULN_META[p.vulnerability] || VULN_META.normal;
                return (
                  <div key={p.person_id} className="rounded-xl border border-slate-700/60 bg-slate-950/40 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-slate-100">
                        {vm.emoji} {p.display_name}
                      </span>
                      <span
                        className={[
                          "shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase ring-1",
                          vm.cls,
                        ].join(" ")}
                        title={`Risk weight ${vm.factor}`}
                      >
                        {vm.label} {vm.factor}
                      </span>
                    </div>
                    <p className="mt-1 text-[11px] text-slate-400">
                      Last activity: <span className="text-slate-200">{la ? `${la.room.replace("_", " ")} · ${timeAgo(la.timestamp)}` : "—"}</span>
                    </p>
                    {p.emergency_contacts?.length > 0 && (
                      <p className="mt-0.5 text-[10px] text-slate-500">
                        ☎ Family: {p.emergency_contacts.join(", ")}
                      </p>
                    )}
                  </div>
                );
              })}
              {profiles.length === 0 && (
                <p className="text-xs text-slate-500">No one configured — pick "Who's home" above.</p>
              )}
              {safety?.vulnerable_alone && (
                <p className="rounded-lg bg-rose-500/10 px-2.5 py-1.5 text-[11px] text-rose-300">
                  ⚠ A vulnerable person is home alone — every concern is escalated ×{safety?.vulnerability_factor}.
                </p>
              )}
            </div>
          </div>

          {/* How safety is judged — intuitive legend */}
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              How Alexa Decides
            </p>
            <ol className="flex flex-col gap-1.5 text-[11px] text-slate-400">
              <li><span className="text-slate-200">1. Learns</span> the daily routine from the same engine as Pattern Recognition.</li>
              <li><span className="text-slate-200">2. Detects</span> safety, health & security concerns.</li>
              <li><span className="text-slate-200">3. Escalates</span> each concern by who's home (elderly ×2, expecting ×1.8, child ×1.7).</li>
              <li><span className="text-slate-200">4. Acts</span> — secures the home and alerts family on its own.</li>
            </ol>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {Object.entries(STATUS_META).map(([k, v]) => (
                <span key={k} className={["rounded px-1.5 py-0.5 text-[9px] font-semibold", v.bg, v.text].join(" ")}>
                  {v.emoji} {v.label}
                </span>
              ))}
            </div>
          </div>

          {/* Activity timeline */}
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Activity Timeline
            </p>
            <ul className="flex max-h-[320px] flex-col gap-1 overflow-y-auto">
              {(data?.timeline || []).slice(0, 25).map((e, i) => (
                <li key={i} className="flex items-center gap-2 text-[11px]">
                  <span className="w-12 shrink-0 text-slate-500">
                    {new Date(e.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                  <span>{DEVICE_META[e.device_id]?.icon || "•"}</span>
                  <span className="truncate text-slate-300">
                    {DEVICE_META[e.device_id]?.label || e.device_id} · {e.action}
                  </span>
                </li>
              ))}
              {(!data?.timeline || data.timeline.length === 0) && (
                <li className="text-xs text-slate-500">No recent activity.</li>
              )}
            </ul>
          </div>

          {/* Patterns learned */}
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Learned Routines
            </p>
            <p className="mt-1 text-2xl font-bold text-slate-100">
              {data?.patterns_count ?? 0}
            </p>
            <p className="text-[10px] text-slate-500">
              deterministic patterns (same engine as Pattern Recognition)
            </p>
          </div>
        </aside>
      </div>

      {/* Alexa stacked notifications (reused from the patterns feature) */}
      <AlexaNotification
        notifications={alexaQueue}
        onDismiss={(id) => setAlexaQueue((q) => q.filter((n) => n.id !== id))}
        onDismissAll={() => setAlexaQueue([])}
        maxVisible={4}
      />

      {toast && (
        <div
          className={[
            "fixed bottom-5 left-1/2 -translate-x-1/2 rounded-xl px-4 py-2 text-sm font-medium shadow-xl",
            toast.ok ? "bg-emerald-500/90 text-white" : "bg-red-500/90 text-white",
          ].join(" ")}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
