"""
Behavior analysis engine for detecting cognitive load from interaction patterns.

Analyzes signals like:
- Fast/aggressive scrolling → frustration or searching behavior
- Rapid tapping → impatience or agitation
- Long idle periods → fatigue or distraction
- Erratic swipe patterns → frustration or high cognitive load
"""
from services.behavior.models import BehaviorSignal, BehaviorAnalysisResult, CognitiveLoad


class BehaviorEngine:
    """Processes interaction signals to determine cognitive load and agitation."""

    # Thresholds for signal classification
    SCROLL_SPEED_HIGH = 0.7
    TAP_FREQUENCY_HIGH = 3.0
    IDLE_DURATION_LONG = 10000  # ms
    AGITATION_DECAY = 0.9

    def __init__(self):
        self._signal_history: list[BehaviorSignal] = []
        self._max_history = 50

    def analyze(self, signals: list[BehaviorSignal]) -> BehaviorAnalysisResult:
        """Analyze a batch of behavioral signals."""
        if not signals:
            return BehaviorAnalysisResult(
                cognitive_load=CognitiveLoad.LOW,
                agitation_level=0.0,
                patterns_detected=[],
                confidence=0.3,
            )

        # Store signals
        self._signal_history.extend(signals)
        if len(self._signal_history) > self._max_history:
            self._signal_history = self._signal_history[-self._max_history:]

        patterns = []
        agitation_scores = []

        for signal in signals:
            if signal.signal_type == "scroll":
                score = self._analyze_scroll(signal)
                if score > 0.6:
                    patterns.append("fast_scrolling")
                agitation_scores.append(score)

            elif signal.signal_type == "tap":
                score = self._analyze_tap(signal)
                if score > 0.6:
                    patterns.append("aggressive_tapping")
                agitation_scores.append(score)

            elif signal.signal_type == "idle":
                score = self._analyze_idle(signal)
                if score > 0.5:
                    patterns.append("prolonged_inactivity")
                # Idle REDUCES agitation — push it negative
                agitation_scores.append(-score * 0.5)

            elif signal.signal_type == "swipe":
                score = self._analyze_swipe(signal)
                if score > 0.6:
                    patterns.append("erratic_swiping")
                agitation_scores.append(score)

        # Calculate overall agitation
        avg_agitation = (
            sum(agitation_scores) / len(agitation_scores) if agitation_scores else 0.0
        )
        avg_agitation = max(0.0, min(1.0, avg_agitation))

        # Special case: if ALL signals are idle, force LOW
        all_idle = all(s.signal_type == "idle" for s in signals)
        if all_idle and any(s.duration_ms >= 15000 for s in signals):
            cognitive_load = CognitiveLoad.LOW
            avg_agitation = 0.0
            patterns.append("prolonged_inactivity")
        else:
            cognitive_load = self._agitation_to_cognitive_load(avg_agitation)

        return BehaviorAnalysisResult(
            cognitive_load=cognitive_load,
            agitation_level=round(avg_agitation, 3),
            patterns_detected=list(set(patterns)),
            confidence=min(0.95, 0.5 + len(signals) * 0.05),
        )

    def _analyze_scroll(self, signal: BehaviorSignal) -> float:
        """Score scroll agitation (0-1). Fast scrolling = high agitation."""
        speed_score = signal.intensity
        frequency_score = min(1.0, signal.frequency / 5.0)
        return speed_score * 0.6 + frequency_score * 0.4

    def _analyze_tap(self, signal: BehaviorSignal) -> float:
        """Score tap agitation. Rapid, hard taps = frustration."""
        intensity_score = signal.intensity
        frequency_score = min(1.0, signal.frequency / self.TAP_FREQUENCY_HIGH)
        return intensity_score * 0.5 + frequency_score * 0.5

    def _analyze_idle(self, signal: BehaviorSignal) -> float:
        """Score idle behavior. Long idle can indicate fatigue/distraction."""
        duration_score = min(1.0, signal.duration_ms / self.IDLE_DURATION_LONG)
        return duration_score

    def _analyze_swipe(self, signal: BehaviorSignal) -> float:
        """Score swipe agitation. Erratic swipes = frustration."""
        return signal.intensity * 0.7 + min(1.0, signal.frequency / 4.0) * 0.3

    def _agitation_to_cognitive_load(self, agitation: float) -> CognitiveLoad:
        """Map agitation level to cognitive load category."""
        if agitation < 0.25:
            return CognitiveLoad.LOW
        elif agitation < 0.5:
            return CognitiveLoad.MODERATE
        elif agitation < 0.75:
            return CognitiveLoad.HIGH
        else:
            return CognitiveLoad.OVERLOADED


# Singleton
behavior_engine = BehaviorEngine()
