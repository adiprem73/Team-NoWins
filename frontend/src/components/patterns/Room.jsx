import DeviceTile from "./DeviceTile.jsx";

// A room zone on the floor plan. Renders its label, accent, and device tiles.
export default function Room({ room, devices, activeSet, anomalyMap, onToggle, busy }) {
  return (
    <div
      className="relative flex flex-col rounded-2xl border border-slate-700/60 bg-slate-900/40 p-3 shadow-lg"
      style={{ gridColumn: room.col, gridRow: room.row }}
    >
      <div className="mb-2 flex items-center gap-2">
        <span
          className="h-2.5 w-2.5 rounded-full"
          style={{ background: room.accent, boxShadow: `0 0 8px ${room.accent}` }}
        />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
          {room.name}
        </h3>
      </div>

      <div className="grid flex-1 content-start gap-2">
        {devices.map((d) => (
          <DeviceTile
            key={d.id}
            device={d}
            isOn={activeSet.has(d.id)}
            anomaly={anomalyMap.get(d.id)}
            onToggle={onToggle}
            busy={busy}
          />
        ))}
        {devices.length === 0 && (
          <p className="text-[11px] italic text-slate-600">no devices</p>
        )}
      </div>
    </div>
  );
}
