"""Large digit frequency control used by the SDRbridge front panel.

The control intentionally has no dependency on Antrack.  It keeps the same
interaction model: each digit is independently wheel-adjustable, while the
whole value remains a normal Qt signal so it can be used by the hot-control
path without a separate Apply button.
"""

from __future__ import annotations

from PyQt5 import QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QWidget


class _Digit(QLabel):
    stepRequested = QtCore.pyqtSignal(int)

    def __init__(self, step_hz: int, parent=None) -> None:
        super().__init__("0", parent)
        self.step_hz = int(step_hz)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumWidth(23)
        self.setCursor(Qt.PointingHandCursor)
        self._set_style(False)

    def _set_style(self, dimmed: bool) -> None:
        color = "#7f8a94" if dimmed else "#152432"
        self.setStyleSheet(
            f"font-size: 34px; font-weight: 700; color: {color}; "
            "padding: 0 1px;"
        )

    def setDimmed(self, dimmed: bool) -> None:  # noqa: N802
        self._set_style(dimmed)

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta:
            self.stepRequested.emit(self.step_hz if delta > 0 else -self.step_hz)
            event.accept()
        else:
            event.ignore()


class FrequencyControlWidget(QWidget):
    """Display an integer Hz value as ``xxx.xxx.xxx.xxx``.

    ``valueChanged`` is emitted for wheel edits.  ``set_value_hz`` is silent,
    which lets the GUI refresh effective state without feedback loops.
    """

    valueChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._min_hz = 1_000
        self._max_hz = 2_000_000_000
        self._value_hz = 144_300_000
        self._steps = (
            100_000_000_000, 10_000_000_000, 1_000_000_000,
            100_000_000, 10_000_000, 1_000_000,
            100_000, 10_000, 1_000,
            100, 10, 1,
        )
        self._digits: list[_Digit] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for index, step in enumerate(self._steps):
            if index in (3, 6, 9):
                separator = QLabel(".", self)
                separator.setAlignment(Qt.AlignCenter)
                separator.setStyleSheet("font-size: 34px; font-weight: 700; color: #7f8a94;")
                layout.addWidget(separator)
            digit = _Digit(step, self)
            digit.stepRequested.connect(self._apply_delta)
            self._digits.append(digit)
            layout.addWidget(digit)
        layout.addStretch(1)
        self._refresh()

    def set_range_hz(self, minimum_hz: int, maximum_hz: int) -> None:
        self._min_hz = max(1, int(minimum_hz))
        self._max_hz = max(self._min_hz, int(maximum_hz))
        self.set_value_hz(self._value_hz)

    def value_hz(self) -> int:
        return int(self._value_hz)

    def set_value_hz(self, value_hz: int) -> None:
        self._value_hz = max(self._min_hz, min(self._max_hz, int(round(value_hz))))
        self._refresh()

    def _apply_delta(self, delta_hz: int) -> None:
        value = max(self._min_hz, min(self._max_hz, self._value_hz + int(delta_hz)))
        if value == self._value_hz:
            return
        self._value_hz = value
        self._refresh()
        self.valueChanged.emit(self._value_hz)

    def _refresh(self) -> None:
        digits = f"{self._value_hz:012d}"
        first = next((i for i, char in enumerate(digits[:-1]) if char != "0"), len(digits) - 1)
        for index, digit in enumerate(self._digits):
            digit.setText(digits[index])
            digit.setDimmed(index < first)

