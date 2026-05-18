"""Config flow for Anniversary Calculator."""
import logging
import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
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

                # 이름 + 날짜 + 종류가 모두 동일한 항목이 이미 있으면 중복으로 판단
                for existing_entry in self._async_current_entries():
                    if (
                        existing_entry.data.get(CONF_NAME) == name
                        and existing_entry.data.get(CONF_DATE) == date_str
                        and existing_entry.data.get(CONF_TYPE) == anniv_type
                    ):
                        return self.async_abort(reason="already_configured")

                unique_id = f"anniv-{name}-{date_str}"
                await self.async_set_unique_id(unique_id)

                _LOGGER.debug("unique_id: %s, title: %s", unique_id, name)
                return self.async_create_entry(title=name, data=user_input)

        return self._show_user_form(errors)

    async def async_step_import(self, import_info):
        """Handle import from config file."""
        return await self.async_step_user(import_info)

    @callback
    def _show_user_form(self, errors: dict | None = None):
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
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
