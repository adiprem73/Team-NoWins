const MOOD_CONFIG = {
  calm: { emoji: "😌", color: "#E6E6FA", label: "Calm" },
  happy: { emoji: "😊", color: "#FFD700", label: "Happy" },
  stressed: { emoji: "😰", color: "#4A90D9", label: "Stressed" },
  anxious: { emoji: "😟", color: "#7B68EE", label: "Anxious" },
  frustrated: { emoji: "😤", color: "#48D1CC", label: "Frustrated" },
  sad: { emoji: "😢", color: "#FF8C00", label: "Sad" },
  energetic: { emoji: "⚡", color: "#00FF7F", label: "Energetic" },
  tired: { emoji: "😴", color: "#FF8C00", label: "Tired" },
  neutral: { emoji: "😐", color: "#94A3B8", label: "Neutral" },
};

export default function MoodIndicator({ mood, confidence }) {
  const config = MOOD_CONFIG[mood] || MOOD_CONFIG.neutral;

  return (
    <div className="text-center">
      <div
        className="w-20 h-20 rounded-full mx-auto flex items-center justify-center text-4xl mb-3 transition-all duration-500"
        style={{
          backgroundColor: `${config.color}20`,
          boxShadow: `0 0 30px ${config.color}40`,
        }}
      >
        {config.emoji}
      </div>
      <p className="text-lg font-semibold text-white">{config.label}</p>
      <p className="text-sm text-gray-400 mt-1">
        Confidence: {Math.round(confidence * 100)}%
      </p>
      <div className="w-full bg-gray-800 rounded-full h-2 mt-3">
        <div
          className="h-2 rounded-full transition-all duration-500"
          style={{
            width: `${confidence * 100}%`,
            backgroundColor: config.color,
          }}
        />
      </div>
    </div>
  );
}
