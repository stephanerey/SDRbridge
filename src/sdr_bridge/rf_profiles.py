from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .model import DeviceCapabilities


@dataclass(frozen=True, slots=True)
class RFRule:
    rule_id: str
    min_hz: int
    max_hz: int
    priority: int
    enabled: bool = True
    device_id: str | None = None
    antenna: str | None = None
    gains: Mapping[str, float] = field(default_factory=dict)
    agc_enabled: bool | None = None

    def __post_init__(self) -> None:
        if not self.rule_id or self.min_hz >= self.max_hz:
            raise ValueError("invalid RF rule")

    def matches(self, frequency_hz: int, device_id: str) -> bool:
        return self.enabled and self.min_hz <= frequency_hz < self.max_hz and self.device_id in (None, device_id)


class RFProfileSet:
    def __init__(self, rules=()):
        self._rules: list[RFRule] = []
        self.suspended = False
        for rule in rules:
            self.add(rule)

    @property
    def rules(self) -> tuple[RFRule, ...]:
        return tuple(self._rules)

    def add(self, rule: RFRule) -> None:
        for current in self._rules:
            same_device = current.device_id == rule.device_id or current.device_id is None or rule.device_id is None
            overlap = max(current.min_hz, rule.min_hz) < min(current.max_hz, rule.max_hz)
            if current.enabled and rule.enabled and same_device and overlap and current.priority == rule.priority:
                raise ValueError("ambiguous RF rules with equal priority")
        self._rules.append(rule)

    def select(self, frequency_hz: int, device_id: str) -> RFRule | None:
        if self.suspended:
            return None
        candidates = [item for item in self._rules if item.matches(frequency_hz, device_id)]
        return max(candidates, key=lambda item: item.priority) if candidates else None

    def validate_rule(self, rule: RFRule, capabilities: DeviceCapabilities) -> None:
        if rule.antenna is not None and rule.antenna not in capabilities.antennas:
            raise ValueError(f"unsupported antenna: {rule.antenna}")
        for name, value in rule.gains.items():
            if name not in capabilities.gain_ranges:
                raise ValueError(f"unknown gain stage: {name}")
            low, high = capabilities.gain_ranges[name]
            if not low <= value <= high:
                raise ValueError(f"gain {name} out of range")
        if rule.agc_enabled and not capabilities.agc_available:
            raise ValueError("AGC is unavailable")

    def suspend_manual(self) -> None:
        self.suspended = True

    def resume(self) -> None:
        self.suspended = False
