"""Test the feed reminder diagnostic sensor."""
from unittest.mock import patch

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.huckleberry.const import DOMAIN
from huckleberry_api.firebase_types import (
    AtReminderEntry,
    FirebaseFeedDocumentData,
    FirebaseFeedPrefs,
    ReminderIn,
    ReminderV2,
)


async def _setup_entry_with_enabled_sensor(hass: HomeAssistant, mock_huckleberry_api) -> MockConfigEntry:
    """Set up a Huckleberry config entry with the (disabled-by-default) feed reminder sensor enabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
    )
    entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "child_1_feed_reminder",
        config_entry=entry,
        disabled_by=None,
        original_name="Feed reminder",
        suggested_object_id="test_child_feed_reminder",
    )

    with patch(
        "custom_components.huckleberry.HuckleberryAPI",
        return_value=mock_huckleberry_api,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_feed_reminder_exposes_raw_interval_value(hass: HomeAssistant, mock_huckleberry_api):
    """The interval reminder's raw value/flags are exposed unmodified."""
    entry = await _setup_entry_with_enabled_sensor(hass, mock_huckleberry_api)

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator._realtime_data["child_1"].feed_status = FirebaseFeedDocumentData(
        prefs=FirebaseFeedPrefs(
            reminderV2=ReminderV2(
                mode="in",
                inReminder=ReminderIn(
                    value=180,
                    daytimeOnly=True,
                    enabled=True,
                    sound=True,
                    vibration=False,
                    days=["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
                ),
            ),
        ),
    )
    coordinator.async_set_updated_data(dict(coordinator._realtime_data))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_feed_reminder")
    assert state is not None
    assert state.state == "in"
    assert state.attributes["interval_enabled"] is True
    assert state.attributes["interval_value_raw"] == 180
    assert state.attributes["interval_daytime_only"] is True
    assert state.attributes["interval_days"] == ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    assert "at_times_raw" not in state.attributes


async def test_feed_reminder_exposes_raw_at_times(hass: HomeAssistant, mock_huckleberry_api):
    """The at-specific-times reminder's raw entries are exposed unmodified."""
    entry = await _setup_entry_with_enabled_sensor(hass, mock_huckleberry_api)

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator._realtime_data["child_1"].feed_status = FirebaseFeedDocumentData(
        prefs=FirebaseFeedPrefs(
            reminderV2=ReminderV2(
                mode="at",
                atReminder={
                    "0": AtReminderEntry(value=480, enabled=True, sound=True, vibration=False, days=["Mon"]),
                },
            ),
        ),
    )
    coordinator.async_set_updated_data(dict(coordinator._realtime_data))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_feed_reminder")
    assert state is not None
    assert state.state == "at"
    assert state.attributes["at_times_raw"]["0"]["value_raw"] == 480
    assert state.attributes["at_times_raw"]["0"]["enabled"] is True
    assert state.attributes["at_times_raw"]["0"]["days"] == ["Mon"]
    assert "interval_value_raw" not in state.attributes


async def test_feed_reminder_no_attributes_when_unset(hass: HomeAssistant, mock_huckleberry_api):
    """No reminder configured means no state and no attributes, not an error."""
    entry = await _setup_entry_with_enabled_sensor(hass, mock_huckleberry_api)

    state = hass.states.get("sensor.test_child_feed_reminder")
    assert state is not None
    assert state.state == "unknown"
