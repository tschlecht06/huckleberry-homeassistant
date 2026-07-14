"""Test the next feed due sensor."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.huckleberry.const import DOMAIN
from huckleberry_api.firebase_types import (
    FirebaseFeedDocumentData,
    FirebaseFeedPrefs,
    FirebaseLastBottleData,
    FirebaseLastNursingData,
    ReminderIn,
    ReminderV2,
)


async def _setup_entry(hass: HomeAssistant, mock_huckleberry_api) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.huckleberry.HuckleberryAPI",
        return_value=mock_huckleberry_api,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def _set_feed_status(coordinator, **prefs_kwargs) -> None:
    coordinator._realtime_data["child_1"].feed_status = FirebaseFeedDocumentData(
        prefs=FirebaseFeedPrefs(**prefs_kwargs),
    )
    coordinator.async_set_updated_data(dict(coordinator._realtime_data))


async def test_next_feed_due_computes_from_last_bottle_plus_interval(hass: HomeAssistant, mock_huckleberry_api):
    """180-minute interval reminder + last bottle time predicts the next feed."""
    entry = await _setup_entry(hass, mock_huckleberry_api)
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    _set_feed_status(
        coordinator,
        lastBottle=FirebaseLastBottleData(
            mode="bottle", start=1700000000, bottleAmount=120.0, bottleUnits="ml", bottleType="Formula", offset=0,
        ),
        reminderV2=ReminderV2(
            mode="in",
            inReminder=ReminderIn(
                value=180, daytimeOnly=False, enabled=True, sound=True, vibration=False,
                days=["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            ),
        ),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_next_feed_due")
    assert state is not None
    expected = datetime.fromtimestamp(1700000000, tz=timezone.utc) + timedelta(minutes=180)
    assert state.state == expected.isoformat()
    assert state.attributes["reminder_mode"] == "in"
    assert state.attributes["interval_minutes"] == 180


async def test_next_feed_due_uses_more_recent_of_bottle_or_nursing(hass: HomeAssistant, mock_huckleberry_api):
    """The later of last bottle / last nursing start is used as the base time."""
    entry = await _setup_entry(hass, mock_huckleberry_api)
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    _set_feed_status(
        coordinator,
        lastBottle=FirebaseLastBottleData(
            mode="bottle", start=1700000000, bottleAmount=120.0, bottleUnits="ml", bottleType="Formula", offset=0,
        ),
        lastNursing=FirebaseLastNursingData(start=1700003600, duration=600, leftDuration=300, rightDuration=300),
        reminderV2=ReminderV2(
            mode="in",
            inReminder=ReminderIn(
                value=180, daytimeOnly=False, enabled=True, sound=True, vibration=False,
                days=["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            ),
        ),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_next_feed_due")
    assert state is not None
    expected = datetime.fromtimestamp(1700003600, tz=timezone.utc) + timedelta(minutes=180)
    assert state.state == expected.isoformat()


async def test_next_feed_due_none_when_interval_disabled(hass: HomeAssistant, mock_huckleberry_api):
    """A configured but disabled interval reminder predicts nothing."""
    entry = await _setup_entry(hass, mock_huckleberry_api)
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    _set_feed_status(
        coordinator,
        lastBottle=FirebaseLastBottleData(
            mode="bottle", start=1700000000, bottleAmount=120.0, bottleUnits="ml", bottleType="Formula", offset=0,
        ),
        reminderV2=ReminderV2(
            mode="in",
            inReminder=ReminderIn(
                value=180, daytimeOnly=False, enabled=False, sound=True, vibration=False,
                days=["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            ),
        ),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_next_feed_due")
    assert state is not None
    assert state.state == "unknown"


async def test_next_feed_due_none_for_at_mode(hass: HomeAssistant, mock_huckleberry_api):
    """"at" mode isn't computed yet — its raw units aren't confirmed."""
    entry = await _setup_entry(hass, mock_huckleberry_api)
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    _set_feed_status(
        coordinator,
        lastBottle=FirebaseLastBottleData(
            mode="bottle", start=1700000000, bottleAmount=120.0, bottleUnits="ml", bottleType="Formula", offset=0,
        ),
        reminderV2=ReminderV2(mode="at"),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_next_feed_due")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["reminder_mode"] == "at"


async def test_next_feed_due_none_when_no_last_feed(hass: HomeAssistant, mock_huckleberry_api):
    """No last bottle or nursing recorded means no prediction, not an error."""
    entry = await _setup_entry(hass, mock_huckleberry_api)
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    _set_feed_status(
        coordinator,
        reminderV2=ReminderV2(
            mode="in",
            inReminder=ReminderIn(
                value=180, daytimeOnly=False, enabled=True, sound=True, vibration=False,
                days=["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            ),
        ),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_next_feed_due")
    assert state is not None
    assert state.state == "unknown"
