// Floor-plan + device catalogue, driven entirely by data so the same canvas
// renders any household. Each household maps device_ids -> a room + render meta.
//
// Grid: a 3-column x 3-row top-view house. Rooms declare their grid placement;
// devices declare which room they live in plus an icon and toggle semantics.

export const ROOMS = {
  garden: { name: "Garden", col: "1 / 2", row: "1 / 2", accent: "#22c55e" },
  son_room: {
    name: "Son's Room",
    col: "2 / 3",
    row: "1 / 2",
    accent: "#a855f7",
  },
  bedroom: { name: "Bedroom", col: "3 / 4", row: "1 / 2", accent: "#6366f1" },
  porch: { name: "Porch", col: "1 / 2", row: "2 / 3", accent: "#eab308" },
  living_room: {
    name: "Living Room",
    col: "2 / 4",
    row: "2 / 3",
    accent: "#38bdf8",
  },
  entrance: { name: "Entrance", col: "1 / 2", row: "3 / 4", accent: "#f97316" },
  utility: { name: "Utility", col: "2 / 4", row: "3 / 4", accent: "#94a3b8" },
};

// Per device-type rendering + on/off action semantics.
export const DEVICE_KIND = {
  fan: { icon: "🌀", onAction: "ON", offAction: "OFF", onColor: "#38bdf8" },
  light: { icon: "💡", onAction: "ON", offAction: "OFF", onColor: "#fde047" },
  ac: { icon: "❄️", onAction: "ON", offAction: "OFF", onColor: "#7dd3fc" },
  tv: { icon: "📺", onAction: "ON", offAction: "OFF", onColor: "#a78bfa" },
  motor: { icon: "🛢️", onAction: "ON", offAction: "OFF", onColor: "#fb923c" },
  door: {
    icon: "🚪",
    onAction: "OPEN",
    offAction: "CLOSE",
    onColor: "#f87171",
  },
};

// Households: each device has id, label, type, room.
export const HOUSEHOLDS = {
  H001: {
    label: "H001 · Son Departure Home",
    people: ["father", "mother", "son"],
    devices: [
      { id: "son_room_fan", label: "Fan", type: "fan", room: "son_room" },
      { id: "son_room_light", label: "Light", type: "light", room: "son_room" },
      { id: "living_room_ac", label: "AC", type: "ac", room: "living_room" },
      { id: "living_room_tv", label: "TV", type: "tv", room: "living_room" },
      { id: "porch_light", label: "Porch Light", type: "light", room: "porch" },
      {
        id: "water_motor",
        label: "Water Motor",
        type: "motor",
        room: "utility",
      },
    ],
  },
  H002: {
    label: "H002 · AC / Motor / Light Home",
    people: ["father", "mother"],
    devices: [
      { id: "bedroom_ac", label: "Bedroom AC", type: "ac", room: "bedroom" },
      {
        id: "living_room_light",
        label: "Light",
        type: "light",
        room: "living_room",
      },
      { id: "living_room_ac", label: "AC", type: "ac", room: "living_room" },
      {
        id: "garden_light",
        label: "Garden Light",
        type: "light",
        room: "garden",
      },
      { id: "porch_light", label: "Porch Light", type: "light", room: "porch" },
      {
        id: "borewell_motor",
        label: "Borewell Motor",
        type: "motor",
        room: "utility",
      },
      { id: "front_door", label: "Front Door", type: "door", room: "entrance" },
    ],
  },
};

// Which rooms to render for a given household (only rooms that hold a device).
export function roomsForHousehold(householdId) {
  const used = new Set(HOUSEHOLDS[householdId].devices.map((d) => d.room));
  return Object.entries(ROOMS)
    .filter(([key]) => used.has(key))
    .map(([key, room]) => ({ key, ...room }));
}
