import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../patternsApi.js";
import TopBar from "../components/patterns/TopBar.jsx";
import HouseFloor from "../components/patterns/HouseFloor.jsx";
import SidePanel from "../components/patterns/SidePanel.jsx";
import AlexaNotification from "../components/patterns/AlexaNotification.jsx";

function nowHHMM() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function Patterns() {
  const [householdId, setHouseholdId] = useState("H001");
  const [simTime, setSimTime] = useState(nowHHMM());
  const [state, setState] = useState(null);
  const [patterns, setPatterns] = useState(null);
  const [context, setContext] = useState(null);
  const [events, setEvents] = useState(null);
  // The user-painted "what-if" scenario: which devices are ON right now.
  // Local only — toggling never writes to the backend, so the demo data is
  // never polluted. Hitting "Go" evaluates this against the learned patterns.
  const [draftActive, setDraftActive] = useState(() => new Set());
  // True when the draft state or clock changed since the last evaluation.
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState(true);
  const [toast, setToast] = useState(null);
  // Alexa-voice popup driven by the LLM narrator endpoint.
  const [alexa, setAlexa] = useState(null);

  const flash = useCallback((msg, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 2600);
  }, []);

  // Ask the backend to phrase a context as a spoken Alexa line, then show it
  // as a notification. Never throws — narration is best-effort.
  const speak = useCallback(async (ctx) => {
    if (!ctx) return;
    try {
      const n = await api.narrate(ctx);
      setAlexa({
        id: Date.now(),
        text: n.alexa_response,
        explanation: n.explanation,
        llmPowered: n.llm_powered,
        tone: (ctx.anomalies?.length || 0) > 0 ? "alert" : "calm",
      });
    } catch {
      /* narration is optional; ignore failures */
    }
  }, []);

  // Evaluate the current draft scenario (devices + clock) against the learned
  // patterns. This is the "Go" action — the heart of the flow.
  const runCheck = useCallback(
    async (
      hid = householdId,
      time = simTime,
      active = draftActive,
      people = state?.people_home,
    ) => {
      setBusy(true);
      try {
        const c = await api.evaluate(hid, {
          at: time,
          activeDevices: [...active],
          peopleHome: people || {},
        });
        setContext(c);
        setDirty(false);
        setConnected(true);
        speak(c);
        return c;
      } catch (e) {
        setConnected(false);
        flash(`Evaluation failed — is the backend running? (${e.message})`, false);
      } finally {
        setBusy(false);
      }
    },
    [householdId, simTime, draftActive, state, flash, speak],
  );

  // Load reference data (patterns, persisted snapshot, events) and seed the
  // draft scenario from the snapshot so the floor plan starts populated, then
  // run an initial evaluation so the panel isn't empty.
  const loadAll = useCallback(
    async (hid = householdId, time = simTime) => {
      setBusy(true);
      try {
        const [s, p, e] = await Promise.all([
          api.getState(hid),
          api.getPatterns(hid),
          api.getEvents(hid),
        ]);
        setState(s);
        setPatterns(p);
        setEvents(e);
        const draft = new Set(s?.active_devices || []);
        setDraftActive(draft);
        setConnected(true);
        const c = await api.evaluate(hid, {
          at: time,
          activeDevices: [...draft],
          peopleHome: s?.people_home || {},
        });
        setContext(c);
        setDirty(false);
        speak(c);
      } catch (e) {
        setConnected(false);
        flash(
          `Cannot reach API — is the backend running? (${e.message})`,
          false,
        );
      } finally {
        setBusy(false);
      }
    },
    [householdId, simTime, flash, speak],
  );

  // Initial + on household change.
  useEffect(() => {
    loadAll(householdId, simTime);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [householdId]);

  // The floor plan reflects the user's painted scenario.
  const activeSet = draftActive;

  const anomalyMap = useMemo(() => {
    const m = new Map();
    (context?.anomalies || []).forEach((a) => {
      if (a.device) m.set(a.device, a);
    });
    return m;
  }, [context]);

  // Toggle a device in the *draft* scenario — local only, no backend write.
  const toggleDraft = useCallback((device) => {
    setDraftActive((prev) => {
      const next = new Set(prev);
      if (next.has(device.id)) next.delete(device.id);
      else next.add(device.id);
      return next;
    });
    setDirty(true);
  }, []);

  // Changing the clock marks the scenario dirty; the user re-runs with "Go".
  const handleSimTime = useCallback((t) => {
    setSimTime(t);
    setDirty(true);
  }, []);

  const handleSeed = useCallback(async () => {
    setBusy(true);
    try {
      const res = await api.seed(householdId);
      flash(
        `Seeded ${res.events_stored} events · ${res.patterns_extracted} patterns`,
      );
      await loadAll(householdId, simTime);
    } catch (e) {
      flash(`Seed failed: ${e.message}`, false);
    } finally {
      setBusy(false);
    }
  }, [householdId, simTime, loadAll, flash]);

  return (
    <div className="mx-auto flex min-h-full max-w-[1400px] flex-col gap-4 p-4">
      <TopBar
        householdId={householdId}
        onHouseholdChange={setHouseholdId}
        simTime={simTime}
        onSimTimeChange={handleSimTime}
        peopleHome={state?.people_home}
        onSeed={handleSeed}
        onRun={() => runCheck()}
        dirty={dirty}
        busy={busy}
        connected={connected}
      />

      <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-[1fr_380px]">
        <main className="flex flex-col gap-3">
          <HouseFloor
            householdId={householdId}
            activeSet={activeSet}
            anomalyMap={anomalyMap}
            onToggle={toggleDraft}
            busy={busy}
          />
          <Legend dirty={dirty} />
        </main>

        <SidePanel
          context={context}
          patterns={patterns}
          state={state}
          events={events}
          loading={busy}
        />
      </div>

      {toast && (
        <div
          className={[
            "fixed bottom-5 left-1/2 -translate-x-1/2 rounded-xl px-4 py-2 text-sm font-medium shadow-xl",
            toast.ok
              ? "bg-emerald-500/90 text-white"
              : "bg-red-500/90 text-white",
          ].join(" ")}
        >
          {toast.msg}
        </div>
      )}

      <AlexaNotification notification={alexa} onClose={() => setAlexa(null)} />
    </div>
  );
}

function Legend({ dirty }) {
  const items = [
    { c: "border-slate-700 bg-slate-800/40", t: "Off" },
    { c: "active-glow border-sky-400/50 bg-sky-400/10", t: "On" },
    { c: "anomaly-pulse border-red-500/70 bg-red-500/10", t: "Anomaly" },
  ];
  return (
    <div className="flex items-center gap-4 rounded-xl border border-slate-700/50 bg-slate-900/40 px-4 py-2 text-[11px] text-slate-400">
      <span className="font-semibold uppercase tracking-wider text-slate-500">
        Legend
      </span>
      {items.map((i) => (
        <span key={i.t} className="flex items-center gap-1.5">
          <span className={`h-4 w-6 rounded-md border ${i.c}`} />
          {i.t}
        </span>
      ))}
      <span className="ml-auto text-slate-500">
        {dirty
          ? "⚠ Scenario changed — hit Go to re-check anomalies"
          : "Paint device states · set the clock · hit Go to detect anomalies"}
      </span>
    </div>
  );
}
