import { Lightbulb, Volume2, Bell } from "lucide-react";

export default function EnvironmentPanel({ environment }) {
  if (!environment) {
    return (
      <div className="text-center text-gray-500 py-4">
        <p className="text-sm">Waiting for mood detection...</p>
      </div>
    );
  }

  // Normalize: handle both formats
  // From orchestrator: { light_color, light_brightness, music_genre, ... }
  // From devices/adjust: { light_color, light_brightness, music_genre, ... }
  const lightColor = environment.light_color || "#FFFFFF";
  const lightBrightness = environment.light_brightness ?? 65;
  const lightTemp = environment.light_temperature_k ?? 4000;
  const musicGenre = environment.music_genre || null;
  const musicVolume = environment.music_volume ?? 0;
  const notificationMode = environment.notification_mode || "normal";
  const reasoning = environment.reasoning || "";

  return (
    <div className="space-y-4">
      {/* Light preview */}
      <div className="flex items-center gap-3">
        <div
          className="w-8 h-8 rounded-full border border-gray-700"
          style={{
            backgroundColor: lightColor,
            opacity: lightBrightness / 100,
            boxShadow: `0 0 12px ${lightColor}60`,
          }}
        />
        <div className="flex-1">
          <div className="flex items-center gap-1">
            <Lightbulb className="w-3 h-3 text-yellow-400" />
            <span className="text-xs text-gray-400">Light</span>
          </div>
          <p className="text-sm text-white">
            {lightBrightness}% · {lightTemp}K
          </p>
        </div>
      </div>

      {/* Music */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center">
          <Volume2 className="w-4 h-4 text-indigo-400" />
        </div>
        <div className="flex-1">
          <span className="text-xs text-gray-400">Music</span>
          <p className="text-sm text-white">
            {musicGenre ? `${musicGenre} · ${musicVolume}%` : "Off"}
          </p>
        </div>
      </div>

      {/* Notifications */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center">
          <Bell className="w-4 h-4 text-amber-400" />
        </div>
        <div className="flex-1">
          <span className="text-xs text-gray-400">Notifications</span>
          <p className="text-sm text-white capitalize">
            {notificationMode}
          </p>
        </div>
      </div>

      {/* Reasoning */}
      {reasoning && (
        <p className="text-xs text-gray-500 italic border-t border-gray-800 pt-3 mt-3">
          "{reasoning}"
        </p>
      )}
    </div>
  );
}
