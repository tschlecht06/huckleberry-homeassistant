"""Test the bottle total today sensor."""
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.huckleberry.const import DOMAIN
from huckleberry_api.firebase_types import (
    FirebaseBottleFeedIntervalData,
    FirebaseBreastFeedIntervalData,
)


async def _setup_entry(hass: HomeAssistant, mock_huckleberry_api) -> MockConfigEntry:
    """Set up a Huckleberry config entry against the given mock API."""
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


async def test_bottle_total_today_sums_ml_entries(hass: HomeAssistant, mock_huckleberry_api):
    """Bottle entries logged in mL are summed as-is."""
    mock_huckleberry_api.list_feed_intervals = AsyncMock(
        return_value=[
            FirebaseBottleFeedIntervalData(
                mode="bottle", start=1700000000, amount=90, units="ml", bottleType="Formula", offset=0,
            ),
            FirebaseBottleFeedIntervalData(
                mode="bottle", start=1700003600, amount=120, units="ml", bottleType="Formula", offset=0,
            ),
        ]
    )

    await _setup_entry(hass, mock_huckleberry_api)

    state = hass.states.get("sensor.test_child_bottle_total_today")
    assert state is not None
    assert state.state == "210.0"
    assert state.attributes["entries"] == 2


async def test_bottle_total_today_converts_oz_to_ml(hass: HomeAssistant, mock_huckleberry_api):
    """Bottle entries logged in oz are converted to mL before summing."""
    mock_huckleberry_api.list_feed_intervals = AsyncMock(
        return_value=[
            FirebaseBottleFeedIntervalData(
                mode="bottle", start=1700000000, amount=4, units="oz", bottleType="Formula", offset=0,
            ),
        ]
    )

    await _setup_entry(hass, mock_huckleberry_api)

    state = hass.states.get("sensor.test_child_bottle_total_today")
    assert state is not None
    assert state.state == "118.3"
    assert state.attributes["entries"] == 1


async def test_bottle_total_today_ignores_non_bottle_intervals(hass: HomeAssistant, mock_huckleberry_api):
    """Nursing/breastfeeding intervals should not count toward the bottle total."""
    mock_huckleberry_api.list_feed_intervals = AsyncMock(
        return_value=[
            FirebaseBreastFeedIntervalData(
                mode="breast", start=1700000000, lastSide="left", leftDuration=300, rightDuration=0, offset=0,
            ),
            FirebaseBottleFeedIntervalData(
                mode="bottle", start=1700003600, amount=60, units="ml", bottleType="Formula", offset=0,
            ),
        ]
    )

    await _setup_entry(hass, mock_huckleberry_api)

    state = hass.states.get("sensor.test_child_bottle_total_today")
    assert state is not None
    assert state.state == "60.0"
    assert state.attributes["entries"] == 1


async def test_bottle_total_today_zero_when_no_entries(hass: HomeAssistant, mock_huckleberry_api):
    """With no bottle entries logged today, the total is zero (not unknown)."""
    await _setup_entry(hass, mock_huckleberry_api)  # default mock returns []

    state = hass.states.get("sensor.test_child_bottle_total_today")
    assert state is not None
    assert state.state == "0.0"
    assert state.attributes["entries"] == 0


async def test_bottle_total_today_preserves_last_value_on_api_error(hass: HomeAssistant, mock_huckleberry_api):
    """A transient list_feed_intervals failure should not blank out the last known total."""
    mock_huckleberry_api.list_feed_intervals = AsyncMock(
        return_value=[
            FirebaseBottleFeedIntervalData(
                mode="bottle", start=1700000000, amount=90, units="ml", bottleType="Formula", offset=0,
            ),
        ]
    )

    entry = await _setup_entry(hass, mock_huckleberry_api)

    state = hass.states.get("sensor.test_child_bottle_total_today")
    assert state.state == "90.0"

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    mock_huckleberry_api.list_feed_intervals = AsyncMock(side_effect=RuntimeError("boom"))
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_child_bottle_total_today")
    assert state.state == "90.0"
