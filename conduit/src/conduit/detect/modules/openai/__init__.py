"""OpenAI detect module — folds former vendor-signal-registry workers."""

from __future__ import annotations

from conduit.detect.models import ChangeSignal
from conduit.detect.modules.base import DetectContext, DetectModule
from conduit.detect.modules.openai.normalize import default_rules_for, signal_to_event
from conduit.detect.modules.openai.workers import ALL_WORKERS


def _align_dependency_bump_from_installed(
    rules: list[dict],
    *,
    installed: dict[str, str],
) -> list[dict]:
    """Prefer the consumer's declared version as DEPENDENCY_BUMP.from_version."""
    out: list[dict] = []
    for rule in rules:
        rule = dict(rule)
        if rule.get("type") == "DEPENDENCY_BUMP":
            pkg = str(rule.get("package") or "").lower()
            for name, ver in installed.items():
                if name.lower() == pkg and ver:
                    rule["from_version"] = ver
                    break
        out.append(rule)
    return out


class OpenAIModule(DetectModule):
    name = "openai"
    packages = ["openai"]

    def run(self, ctx: DetectContext) -> list[ChangeSignal]:
        warnings: list[str] = ctx.extra.setdefault("warnings", [])
        signals: list[ChangeSignal] = []
        for worker_cls in ALL_WORKERS:
            worker = worker_cls()
            try:
                raw_list = worker.run(demo=ctx.demo)
            except Exception as exc:
                warnings.append(f"openai worker {worker.name}: {exc}")
                continue
            if not raw_list and not ctx.demo:
                if worker.name == "ModelPollingWorker":
                    warnings.append(
                        "openai worker ModelPollingWorker: no signals "
                        "(set OPENAI_API_KEY for live /v1/models polling)"
                    )
                else:
                    warnings.append(
                        f"openai worker {worker.name}: returned 0 signals"
                    )
            for raw in raw_list:
                event = signal_to_event(raw)
                rules = event.rules or default_rules_for(raw)
                rules = _align_dependency_bump_from_installed(
                    list(rules), installed=ctx.installed
                )
                from_v = to_v = None
                if raw.change_type.value == "SDK_MAJOR_BUMP":
                    to_v = str(raw.extra.get("to_version") or raw.replacement_pattern or "")
                    pkg = str(raw.extra.get("package") or raw.affected_pattern or "openai")
                    from_v = None
                    for name, ver in ctx.installed.items():
                        if name.lower() == pkg.lower() and ver:
                            from_v = ver
                            break
                    from_v = from_v or str(raw.extra.get("from_version") or "")
                signals.append(
                    ChangeSignal(
                        source="module:openai",
                        package="openai",
                        change_type=event.change_type,
                        severity=event.severity,
                        from_version=from_v,
                        to_version=to_v,
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
