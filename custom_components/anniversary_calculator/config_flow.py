"""Config flow for Anniversary Calculator."""
import logging
import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_UID,
    CONF_NAME,
    CONF_DATE,
    CONF_TYPE,
    CONF_LUNAR,
    CONF_INTERCAL,
    ANNIV_TYPE,
)

_LOGGER = logging.getLogger(__name__)

DATE_PATTERN_FULL = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_PATTERN_MMDD = re.compile(r"^\d{2}-\d{2}$")


class AnniversaryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Anniversary Calculator."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_ASSUMED

    def __init__(self) -> None:
        """Initialize flow."""
        self._name: str | None = None
        self._date: str | None = None
        self._type: str | None = None
        self._is_lunar: bool | None = None
        self._is_intercal: bool | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return AnniversaryOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            date_str: str = user_input[CONF_DATE]

            # 날짜 포맷 검증
            if not DATE_PATTERN_FULL.match(date_str) and not DATE_PATTERN_MMDD.match(date_str):
                errors[CONF_DATE] = "invalid_date"
            else:
                name: str = user_input[CONF_NAME]
                anniv_type: str = user_input[CONF_TYPE]
                unique_id: str = user_input[CONF_UID]

                # 사용자가 입력한 고유 ID 중복 검사
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                _LOGGER.debug("unique_id: %s, title: %s", unique_id, name)
                return self.async_create_entry(title=name, data=user_input)

        return self._show_user_form(errors)

    @callback
    def _show_user_form(self, errors: dict | None = None):
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_UID): str,
                vol.Required(CONF_DATE): str,
                vol.Required(CONF_TYPE, default="anniversary"): vol.In(ANNIV_TYPE),
                vol.Optional(CONF_LUNAR, default=False): selector.BooleanSelector(
                    selector.BooleanSelectorConfig()
                ),
                vol.Optional(CONF_INTERCAL, default=False): selector.BooleanSelector(
                    selector.BooleanSelectorConfig()
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors or {}
        )


class AnniversaryOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Anniversary Calculator."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            date_str: str = user_input[CONF_DATE]
            if not DATE_PATTERN_FULL.match(date_str) and not DATE_PATTERN_MMDD.match(date_str):
                errors[CONF_DATE] = "invalid_date"
            else:
                return self.async_create_entry(title="", data=user_input)

        data = user_input if user_input is not None else self.config_entry.data

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=data.get(CONF_NAME)): str,
                vol.Required(CONF_DATE, default=data.get(CONF_DATE)): str,
                vol.Required(CONF_TYPE, default=data.get(CONF_TYPE, "anniversary")): vol.In(ANNIV_TYPE),
                vol.Optional(CONF_LUNAR, default=data.get(CONF_LUNAR, False)): selector.BooleanSelector(
                    selector.BooleanSelectorConfig()
                ),
                vol.Optional(CONF_INTERCAL, default=data.get(CONF_INTERCAL, False)): selector.BooleanSelector(
                    selector.BooleanSelectorConfig()
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
