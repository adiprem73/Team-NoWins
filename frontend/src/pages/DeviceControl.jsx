import { useState, useEffect } from "react";
import { Lightbulb, Speaker, Bell, Wifi, WifiOff } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export default function DeviceControl() {
  const [rooms, setRooms] = useState([
    { id: "living-room", name: "Living Room", status: "connected" },
    { id: "bedroom", name: "Bedroom", status: "connected" },
    { id: "office", name: "Home Office", status: "disconnected" },
  ]);

  const [selectedRoom, setSelectedRoom] = useState("living-room");
  const [presets, setPresets] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/devices/presets`)
      .then((res) => res.json())
      .then(setPresets)
      .catch(() => {});
  }, []);

  const applyMood = async (mood) => {
    try {
      const res = await fetch(`${API_BASE}/devices/adjust`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mood,
          cognitive_load: "moderate",
          room_id: selectedRoom,
        }),
      });
      const data = await res.json();
      alert(`Applied "${mood}" environment to ${selectedRoom}:\n${data.environment.reasoning}`);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Device Control</h2>
        <p className="text-gray-400 text-sm">
          Manage rooms and manually apply mood presets
        </p>
      </div>

      {/* Room selector */}
      <div className="flex gap-3">
        {rooms.map((room) => (
          <button
            key={room.id}
            onClick={() => setSelectedRoom(room.id)}
            className={`px-4 py-2 rounded-lg border transition-colors flex items-center gap-2 ${
              selectedRoom === room.id
                ? "border-indigo-500 bg-indigo-900/30 text-white"
                : "border-gray-700 text-gray-400 hover:border-gray-600"
            }`}
          >
            {room.status === "connected" ? (
              <Wifi className="w-3 h-3 text-green-400" />
            ) : (
              <WifiOff className="w-3 h-3 text-red-400" />
            )}
            {room.name}
          </button>
        ))}
      </div>

      {/* Mood presets grid */}
      <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
        <h3 className="font-semibold text-white mb-4">Apply Mood Preset</h3>
        <div className="grid grid-cols-3 gap-3">
          {[
            { mood: "calm", emoji: "😌", color: "#E6E6FA" },
            { mood: "happy", emoji: "😊", color: "#FFD700" },
            { mood: "stressed", emoji: "😰", color: "#4A90D9" },
            { mood: "anxious", emoji: "😟", color: "#7B68EE" },
            { mood: "frustrated", emoji: "😤", color: "#48D1CC" },
            { mood: "sad", emoji: "😢", color: "#FF8C00" },
            { mood: "energetic", emoji: "⚡", color: "#00FF7F" },
            { mood: "tired", emoji: "😴", color: "#FF8C00" },
            { mood: "neutral", emoji: "😐", color: "#94A3B8" },
          ].map(({ mood, emoji, color }) => (
            <button
              key={mood}
              onClick={() => applyMood(mood)}
              className="p-4 rounded-xl border border-gray-700 hover:border-gray-500 transition-all hover:scale-105 text-center"
              style={{ borderColor: `${color}30` }}
            >
              <span className="text-2xl">{emoji}</span>
              <p className="text-sm text-gray-300 capitalize mt-1">{mood}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Device status */}
      <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
        <h3 className="font-semibold text-white mb-4">Connected Devices</h3>
        <div className="space-y-3">
          <DeviceRow icon={Lightbulb} name="Smart Lights" status="online" color="#FBBF24" />
          <DeviceRow icon={Speaker} name="Echo Speaker" status="online" color="#818CF8" />
          <DeviceRow icon={Bell} name="Notification Hub" status="online" color="#F97316" />
        </div>
      </div>
    </div>
  );
}

function DeviceRow({ icon: Icon, name, status, color }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-800/50">
      <Icon className="w-5 h-5" style={{ color }} />
      <span className="flex-1 text-sm text-white">{name}</span>
      <span
        className={`text-xs px-2 py-0.5 rounded-full ${
          status === "online"
            ? "bg-green-900/30 text-green-400"
            : "bg-red-900/30 text-red-400"
        }`}
      >
        {status}
      </span>
    </div>
  );
}
