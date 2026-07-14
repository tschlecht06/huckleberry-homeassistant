"""Feeding reminder entities for Huckleberry.

Exposes the raw `reminderV2` schedule config from `feed/{uid}.prefs` (bottle and
nursing reminders share this slot; `solids_reminderV2` is separate and not
covered here). This is the reminder *configuration* set in the Huckleberry
app — not a computed "next feed due" time. Huckleberry doesn't store a
precomputed next-time for feeding reminders the way it does for nap
"sweetspot" predictions, and the units of `value` inside `inReminder`/
`atReminder` aren't documented by the huckleberry-api library. Attributes here
pass the raw numbers through unmodified rather than guessing at what they mean
— see AGENTS.md's rule against inferring values that originate from
Huckleberry's schema. Once the real units are confirmed against account data,
a computed "next feed" sensor can build on top of this.
"""
from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from .. import HuckleberryDataUpdateCoordinator
from ..entity import HuckleberryBaseEntity
from ..models import HuckleberryChildProfile

REMINDER_MODE_OPTIONS: Final[list[str]] = ["at", "in"]


def build_feed_reminder_sensors(
    coordinator: HuckleberryDataUpdateCoordinator,
    children: list[HuckleberryChildProfile],
) -> list[SensorEntity]:
    """Build feeding reminder sensors."""
    return [HuckleberryFeedReminderSensor(coordinator, child) for child in children]


class HuckleberryFeedReminderSensor(HuckleberryBaseEntity, SensorEntity):
    """Diagnostic sensor exposing the raw feeding reminder schedule."""

    _attr_icon = "mdi:bell-ring-outline"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = REMINDER_MODE_OPTIONS
    _attr_translation_key = "feed_reminder"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: HuckleberryDataUpdateCoordinator, child: HuckleberryChildProfile) -> None:
        super().__init__(coordinator, child)
        self._attr_unique_id = f"{self.child_uid}_feed_reminder"

    def _reminder(self):
        feed_status = self.coordinator.get_feed_status(self.child_uid)
        prefs = feed_status.prefs if feed_status is not None else None
        return prefs.reminderV2 if prefs is not None else None

    @property
    def native_value(self) -> str | None:
        """Return the reminder mode ("at" or "in"), if a reminder is configured."""
        reminder = self._reminder()
        if reminder is None:
            return None
        return reminder.mode

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return the raw reminder schedule, unmodified.

        `*_value_raw` fields are passed through as-is rather than interpreted
        (e.g. as minutes or hours) — their units haven't been confirmed against
        real account data yet.
        """
        reminder = self._reminder()
        if reminder is None:
            return {}

        attributes: dict[str, object] = {}

        if reminder.inReminder is not None:
            attributes["interval_enabled"] = reminder.inReminder.enabled
            attributes["interval_value_raw"] = reminder.inReminder.value
            attributes["interval_daytime_only"] = reminder.inReminder.daytimeOnly
            attributes["interval_days"] = reminder.inReminder.days

        if reminder.atReminder:
            attributes["at_times_raw"] = {
                key: {
                    "value_raw": entry.value,
                    "enabled": entry.enabled,
                    "days": entry.days,
                }
                for key, entry in reminder.atReminder.items()
            }

        return attributes
