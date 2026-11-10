from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

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
    bandwidth_hz: int | None = None
    hysteresis_hz: int = 0

    def __post_init__(self) -> None:
        if not self.rule_id or self.min_hz >= self.max_hz:
            raise ValueError("invalid RF rule")
        if self.bandwidth_hz is not None and self.bandwidth_hz <= 0:
            raise ValueError("RF rule bandwidth must be positive")
        if self.hysteresis_hz < 0:
            raise ValueError("RF rule hysteresis cannot be negative")

    def matches(self, frequency_hz: int, device_id: str) -> bool:
        return self.enabled and self.min_hz <= frequency_hz < self.max_hz and self.device_id in (None, device_id)

    def retains(self, frequency_hz: int, device_id: str) -> bool:
        """Return whether hysteresis keeps an already active rule selected."""
        return (
            self.enabled
            and self.device_id in (None, device_id)
            and self.min_hz - self.hysteresis_hz <= frequency_hz < self.max_hz + self.hysteresis_hz
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "min_hz": self.min_hz,
            "max_hz": self.max_hz,
            "priority": self.priority,
            "enabled": self.enabled,
            "device_id": self.device_id,
            "antenna": self.antenna,
            "gains": dict(self.gains),
            "agc_enabled": self.agc_enabled,
            "bandwidth_hz": self.bandwidth_hz,
            "hysteresis_hz": self.hysteresis_hz,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RFRule":
        return cls(
            rule_id=str(value["rule_id"]),
            min_hz=int(value["min_hz"]),
            max_hz=int(value["max_hz"]),
            priority=int(value.get("priority", 0)),
            enabled=bool(value.get("enabled", True)),
            device_id=value.get("device_id"),
            antenna=value.get("antenna"),
            gains={str(name): float(amount) for name, amount in dict(value.get("gains", {})).items()},
            agc_enabled=value.get("agc_enabled"),
            bandwidth_hz=(None if value.get("bandwidth_hz") is None else int(value["bandwidth_hz"])),
            hysteresis_hz=int(value.get("hysteresis_hz", 0)),
        )


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

    def select(self, frequency_hz: int, device_id: str, active_rule_id: str | None = None) -> RFRule | None:
        if self.suspended:
            return None
        if active_rule_id:
            active = next((item for item in self._rules if item.rule_id == active_rule_id), None)
            if active is not None and active.retains(frequency_hz, device_id):
                return active
        candidates = [item for item in self._rules if item.matches(frequency_hz, device_id)]
        return max(candidates, key=lambda item: item.priority) if candidates else None

    def replace(self, rule: RFRule) -> None:
        previous = list(self._rules)
        self._rules = [item for item in self._rules if item.rule_id != rule.rule_id]
        try:
            self.add(rule)
        except Exception:
            self._rules = previous
            raise

    def remove(self, rule_id: str) -> bool:
        before = len(self._rules)
        self._rules = [item for item in self._rules if item.rule_id != rule_id]
        return len(self._rules) != before

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
        if (
            rule.bandwidth_hz is not None
            and capabilities.bandwidths_hz
            and rule.bandwidth_hz not in capabilities.bandwidths_hz
        ):
            raise ValueError(f"unsupported bandwidth: {rule.bandwidth_hz}")

    def suspend_manual(self) -> None:
        self.suspended = True

    def resume(self) -> None:
        self.suspended = False
