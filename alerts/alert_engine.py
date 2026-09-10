"""
The alert engine — deciding what is worth telling the driver.

THE HARD PART IS STAYING QUIET
------------------------------
A system that alerts whenever a marginally better route appears is worse than
one that never alerts at all: people learn to dismiss it, and then miss the
alert that mattered. The engineering here is mostly about suppression.

The rerouting engine decides what is TRUE. This module decides what is WORTH
SAYING. Keeping them separate means the thresholds below can be tuned — or
handed to the user as a setting — without touching the optimiser.

FIVE GATES, AND WHY EACH EXISTS
-------------------------------
1. ABSOLUTE SAVING     Saving 90 seconds on a 40-minute drive is not worth an
                       interruption. Default: 5 minutes.
2. RELATIVE SAVING     On a 3-hour delivery round, 5 minutes is noise. Requiring
                       a percentage as well as an absolute keeps the rule sane
                       across trip lengths. Default: 10%.
3. COOLDOWN            After any alert, stay silent for a while. Without this,
                       a slowly worsening jam produces a stream of alerts as the
                       saving creeps up. Default: 5 minutes.
                       With an ESCALATION OVERRIDE: if the saving has grown
                       2.5x since the last alert, speak anyway. A plain cooldown
                       suppressed savings of 15, 37 and 46 minutes in testing
                       because a 6-minute alert had just fired — which is
                       exactly when the driver most needs to hear from you.
4. REPEAT SUPPRESSION  If the driver declined this suggestion, do not ask again
                       unless the situation has materially changed — which we
                       define as the saving growing by half again. Nagging is
                       how a useful feature becomes an ignored one.
5. HYSTERESIS          Once rerouted, require a larger margin before rerouting
                       again. Prevents ping-ponging between two routes whose
                       ranking keeps flipping as traffic fluctuates.

Incidents and closures BYPASS gates 1-3: a closed road ahead is not a
suggestion, it is information the driver needs immediately.
"""
import time
from dataclasses import dataclass, field


@dataclass
class AlertPolicy:
    min_saving_min: float = 5.0       # gate 1
    min_saving_pct: float = 10.0      # gate 2
    cooldown_s: float = 300.0         # gate 3
    escalation_factor: float = 2.5    # gate 3 override: re-alert if it gets this much worse
    repeat_growth_factor: float = 1.5  # gate 4
    hysteresis_factor: float = 1.5    # gate 5
    max_alerts_per_trip: int = 5


@dataclass
class Alert:
    kind: str                          # reroute | incident | closure
    severity: str                      # info | moderate | severe
    title: str
    message: str
    action: str
    current_eta_min: float = 0.0
    new_eta_min: float = 0.0
    time_saved_min: float = 0.0
    saved_pct: float = 0.0
    created_at: float = field(default_factory=time.time)
    decision: object = None
    # Set once the driver answers. A suggestion can be taken or refused once:
    # two clients answering the same alert — two tabs in Demo Mode, a double
    # click — would otherwise count one switch twice.
    resolved: str | None = None

    def to_dict(self):
        return {
            "kind": self.kind,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "action": self.action,
            "currentEtaMin": round(self.current_eta_min, 1),
            "newEtaMin": round(self.new_eta_min, 1),
            "timeSavedMin": round(self.time_saved_min, 1),
            "savedPct": round(self.saved_pct, 1),
        }

    def render(self):
        """Plain-text form, matching what the dashboard shows."""
        lines = [f"[{self.severity.upper()}] {self.title}", "", self.message]
        if self.time_saved_min > 0:
            lines += [
                "",
                f"  Current ETA:     {self.current_eta_min:.0f} min",
                f"  Alternative ETA: {self.new_eta_min:.0f} min",
                f"  Time saved:      {self.time_saved_min:.0f} min "
                f"({self.saved_pct:.0f}%)",
            ]
        lines += ["", f"Recommended action: {self.action}"]
        return "\n".join(lines)


class AlertEngine:
    """Stateful: it has to remember what it already said, and what was declined."""

    def __init__(self, policy=None, clock=time.time):
        self.policy = policy or AlertPolicy()
        self.clock = clock
        self.history = []
        self.last_alert_at = None
        self.declined_saving_min = None    # saving the driver last said no to
        self.reroute_count = 0
        self.suppressed = []               # (reason, saving) — for the report

    def new_trip(self):
        """
        Forget the previous journey.

        The cooldown, the reroute cap and "the driver already said no to this"
        are facts about one trip. Held on the engine without this, they carried
        into the next journey: optimise a new route within five minutes of the
        last alert and the first real jam on it was suppressed "within
        cooldown" — which made the demo silently fail on its second run.

        Not called when a reroute is accepted. That is the same journey
        continuing, and the cooldown is exactly what stops the system nagging
        again straight after the driver switched.
        """
        self.history = []
        self.last_alert_at = None
        self.declined_saving_min = None
        self.reroute_count = 0
        self.suppressed = []

    # ------------------------------------------------------------ helpers
    def _suppress(self, reason, decision):
        self.suppressed.append((reason, decision.time_saved_min))
        return None

    def _required_saving(self):
        """Threshold, raised by hysteresis after each reroute already taken."""
        base = self.policy.min_saving_min
        if self.reroute_count:
            base *= self.policy.hysteresis_factor ** self.reroute_count
        return base

    # -------------------------------------------------------------- main
    def consider(self, decision, incident=None):
        """
        Turn a RerouteDecision into an Alert, or into silence.

        Returns an Alert or None. Every suppression is recorded with its reason,
        so the demo can show WHY the system stayed quiet — which is as much the
        point as the alerts it does raise.
        """
        now = self.clock()

        # --- closures and incidents: inform immediately -------------------
        if decision.blocked:
            return self._emit(Alert(
                kind="closure",
                severity="severe",
                title="Road closed ahead",
                message=("The road ahead on your current route is closed. "
                         "A new route has been calculated."),
                action="Switch route",
                current_eta_min=decision.current_eta_min,
                new_eta_min=decision.new_eta_min,
                time_saved_min=max(decision.time_saved_min, 0.0),
                saved_pct=max(decision.saved_pct, 0.0),
                decision=decision,
            ), now)

        if incident is not None:
            return self._emit(Alert(
                kind="incident",
                severity="severe",
                title=f"{incident.get('type', 'Incident').title()} reported",
                message=(f"{incident.get('type', 'An incident').title()} at "
                         f"{incident.get('location', 'a junction')} on your route."),
                action="Consider an alternative route",
                current_eta_min=decision.current_eta_min,
                new_eta_min=decision.new_eta_min,
                time_saved_min=max(decision.time_saved_min, 0.0),
                saved_pct=max(decision.saved_pct, 0.0),
                decision=decision,
            ), now)

        if not decision.should_reroute:
            return self._suppress(decision.reason or "no better route", decision)

        # --- gate 1: absolute saving --------------------------------------
        required = self._required_saving()
        if decision.time_saved_min < required:
            return self._suppress(
                f"saves {decision.time_saved_min:.1f} min, below the "
                f"{required:.1f} min threshold", decision)

        # --- gate 2: relative saving --------------------------------------
        if decision.saved_pct < self.policy.min_saving_pct:
            return self._suppress(
                f"saves only {decision.saved_pct:.1f}% of the remaining journey",
                decision)

        # --- gate 3: cooldown, with an escalation override ------------------
        # A plain cooldown is wrong when the situation deteriorates sharply:
        # measured on the escalating-congestion test, savings of 15, 37 and 46
        # minutes were all suppressed because a 6-minute alert had just fired.
        # So the cooldown yields when the saving has grown several times over —
        # that is no longer the same suggestion, it is a materially worse world.
        if self.last_alert_at is not None:
            elapsed = now - self.last_alert_at
            last_saving = self.history[-1].time_saved_min if self.history else 0.0
            escalated = (last_saving > 0
                         and decision.time_saved_min
                         >= last_saving * self.policy.escalation_factor)
            if elapsed < self.policy.cooldown_s and not escalated:
                return self._suppress(
                    f"within cooldown ({elapsed:.0f}s of "
                    f"{self.policy.cooldown_s:.0f}s)", decision)

        # --- gate 4: already declined this ---------------------------------
        if self.declined_saving_min is not None:
            needed = self.declined_saving_min * self.policy.repeat_growth_factor
            if decision.time_saved_min < needed:
                return self._suppress(
                    f"driver declined a {self.declined_saving_min:.1f} min saving; "
                    f"needs {needed:.1f} min to ask again", decision)

        if len(self.history) >= self.policy.max_alerts_per_trip:
            return self._suppress("alert limit for this trip reached", decision)

        # --- passed every gate --------------------------------------------
        reorder = " by resequencing your remaining stops" if decision.stop_order_changed else ""
        return self._emit(Alert(
            kind="reroute",
            severity="moderate" if decision.saved_pct < 25 else "severe",
            title="Faster route available",
            message=(f"Heavy congestion detected on your current route. "
                     f"An alternative can save about "
                     f"{decision.time_saved_min:.0f} minutes{reorder}."),
            action="Switch route",
            current_eta_min=decision.current_eta_min,
            new_eta_min=decision.new_eta_min,
            time_saved_min=decision.time_saved_min,
            saved_pct=decision.saved_pct,
            decision=decision,
        ), now)

    def _emit(self, alert, now):
        self.history.append(alert)
        self.last_alert_at = now
        return alert

    # ------------------------------------------------------ driver replies
    def accepted(self, alert):
        """Driver took the new route: raise the bar for the next suggestion."""
        self.reroute_count += 1
        self.declined_saving_min = None

    def declined(self, alert):
        """Driver said no: do not ask again until it is materially worse."""
        self.declined_saving_min = alert.time_saved_min

    def report(self):
        return {
            "alerts_raised": len(self.history),
            "reroutes_taken": self.reroute_count,
            "suppressed": len(self.suppressed),
            "suppression_reasons": [r for r, _ in self.suppressed],
        }
