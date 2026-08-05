"""OpenAI detect module — folds former vendor-signal-registry workers."""

from __future__ import annotations

from conduit.detect.models import ChangeSignal
from conduit.detect.modules.base import DetectContext, DetectModule
from conduit.detect.modules.openai.normalize import default_rules_for, signal_to_event
from conduit.detect.modules.openai.workers import ALL_WORKERS


class OpenAIModule(DetectModule):
    name = "openai"
    packages = ["openai"]

    def run(self, ctx: DetectContext) -> list[ChangeSignal]:
        signals: list[ChangeSignal] = []
        for worker_cls in ALL_WORKERS:
            worker = worker_cls()
            try:
                raw_list = worker.run()
            except Exception:
                continue
            for raw in raw_list:
                event = signal_to_event(raw)
                rules = event.rules or default_rules_for(raw)
                signals.append(
                    ChangeSignal(
                        source="module:openai",
                        package="openai",
                        change_type=event.change_type,
                        severity=event.severity,
                        affected_pattern=event.affected_pattern,
                        replacement_pattern=event.replacement_pattern,
                        description=event.description,
                        source_url=event.source_url,
                        deadline=event.deadline,
                        suggested_rules=list(rules),
                        hints={"event_id": event.event_id, "vendor": event.vendor},
                    )
                )
        return signals
