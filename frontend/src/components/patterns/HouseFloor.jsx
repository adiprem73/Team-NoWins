import Room from "./Room.jsx";
import { HOUSEHOLDS, roomsForHousehold } from "../../config/houseLayout.js";

// The top-view 2D floor plan: a 3x3 grid of room zones with device tiles.
export default function HouseFloor({
  householdId,
  activeSet,
  anomalyMap,
  onToggle,
  busy,
}) {
  const rooms = roomsForHousehold(householdId);
  const devices = HOUSEHOLDS[householdId].devices;
  const devicesByRoom = (roomKey) => devices.filter((d) => d.room === roomKey);

  return (
    <div className="relative rounded-3xl border border-slate-700/50 bg-slate-950/40 p-4 shadow-2xl">
      {/* House outline label */}
      <div className="pointer-events-none absolute right-5 top-4 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-600">
        Top View · Live
      </div>

      <div
        className="grid gap-3"
        style={{
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gridTemplateRows: "repeat(3, minmax(140px, 1fr))",
        }}
      >
        {rooms.map((room) => (
          <Room
            key={room.key}
            room={room}
            devices={devicesByRoom(room.key)}
            activeSet={activeSet}
            anomalyMap={anomalyMap}
            onToggle={onToggle}
            busy={busy}
          />
        ))}
      </div>
    </div>
  );
}
