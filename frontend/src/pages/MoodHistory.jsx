import { useState } from "react";
import { Clock } from "lucide-react";

// Demo history data (in production, this would come from a database)
const DEMO_HISTORY = [
  { time: "10:30 AM", mood: "stressed", cognitive_load: "high", trigger: "Speech: 'This deadline is killing me'" },
  { time: "10:35 AM", mood: "stressed", cognitive_load: "overloaded", trigger: "Behavior: aggressive tapping detected" },
  { time: "10:40 AM", mood: "calm", cognitive_load: "moderate", trigger: "Environment adjusted: blue lights + ambient" },
  { time: "11:00 AM", mood: "neutral", cognitive_load: "low", trigger: "Speech: 'Alexa, what's the weather today?'" },
  { time: "12:15 PM", mood: "happy", cognitive_load: "low", trigger: "Speech: 'That lunch was amazing'" },
  { time: "2:00 PM", mood: "tired", cognitive_load: "moderate", trigger: "Behavior: prolonged inactivity" },
  { time: "3:30 PM", mood: "frustrated", cognitive_load: "high", trigger: "Behavior: fast scrolling + rapid tapping" },
];

const MOOD_COLORS = {
  calm: "#E6E6FA",
  happy: "#FFD700",
  stressed: "#4A90D9",
  anxious: "#7B68EE",
  frustrated: "#48D1CC",
  sad: "#FF8C00",
  energetic: "#00FF7F",
  tired: "#FF8C00",
  neutral: "#94A3B8",
};

export default function MoodHistory() {
  const [history] = useState(DEMO_HISTORY);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Mood History</h2>
        <p className="text-gray-400 text-sm">
          Timeline of detected moods and environment adjustments
        </p>
      </div>

      <div className="bg-gray-900 rounded-2xl border border-gray-800 overflow-hidden">
        <div className="divide-y divide-gray-800">
          {history.map((entry, i) => (
            <div key={i} className="p-4 flex items-center gap-4 hover:bg-gray-800/50 transition-colors">
              <div className="flex items-center gap-2 w-24 shrink-0">
                <Clock className="w-3 h-3 text-gray-500" />
                <span className="text-sm text-gray-400">{entry.time}</span>
              </div>

              <div
                className="w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: MOOD_COLORS[entry.mood] }}
              />

              <div className="flex-1">
                <span className="text-sm text-white capitalize font-medium">
                  {entry.mood}
                </span>
                <span className="text-gray-600 mx-2">·</span>
                <span className="text-xs text-gray-400 capitalize">
                  {entry.cognitive_load} load
                </span>
              </div>

              <p className="text-xs text-gray-500 max-w-xs truncate">
                {entry.trigger}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
