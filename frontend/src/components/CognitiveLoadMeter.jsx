const LOAD_LEVELS = {
  low: { value: 25, color: "#4ADE80", label: "Low", description: "Relaxed state" },
  moderate: { value: 50, color: "#FBBF24", label: "Moderate", description: "Normal activity" },
  high: { value: 75, color: "#F97316", label: "High", description: "Heavy mental load" },
  overloaded: { value: 100, color: "#EF4444", label: "Overloaded", description: "Needs intervention" },
};

export default function CognitiveLoadMeter({ level }) {
  const config = LOAD_LEVELS[level] || LOAD_LEVELS.moderate;

  return (
    <div className="text-center">
      {/* Circular gauge */}
      <div className="relative w-24 h-24 mx-auto mb-3">
        <svg className="w-24 h-24 transform -rotate-90" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke="#1F2937"
            strokeWidth="10"
          />
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke={config.color}
            strokeWidth="10"
            strokeDasharray={`${config.value * 2.51} 251`}
            className="transition-all duration-700"
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-bold text-white">{config.value}%</span>
        </div>
      </div>

      <p className="text-lg font-semibold" style={{ color: config.color }}>
        {config.label}
      </p>
      <p className="text-sm text-gray-400 mt-1">{config.description}</p>
    </div>
  );
}
