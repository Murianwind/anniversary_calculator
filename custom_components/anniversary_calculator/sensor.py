"""
Anniversary sensor supporting the lunar calendar.
https://github.com/Murianwind/anniversary_calculator
"""

from datetime import timedelta, date
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import async_track_point_in_utc_time
import homeassistant.util.dt as dt_util

from korean_lunar_calendar import KoreanLunarCalendar

from .const import (
    DOMAIN,
    CONF_UID,
    CONF_NAME,
    CONF_DATE,
    CONF_TYPE,
    CONF_LUNAR,
    CONF_INTERCAL,
    INTERCALATION,
    MODEL,
    MANUFACT,
    ATTRIBUTION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """통합 구성요소의 sensor 플랫폼 Entry 설정"""
    _LOGGER.debug(entry.data)

    date_str: str = entry.data.get(CONF_DATE)
    is_lunar: bool = entry.data.get(CONF_LUNAR)
    is_intercalation: bool = entry.data.get(CONF_INTERCAL)
    anniv_type: str = entry.data.get(CONF_TYPE)
    name: str = entry.data.get(CONF_NAME)
    unique_id: str = entry.data.get(CONF_UID)

    is_mmdd = False
    if dt_util.parse_date(date_str) is None:
        year_added = f"{dt_util.as_local(dt_util.utcnow()).date().year}-{date_str}"
        if dt_util.parse_date(year_added) is not None:
            date_str = year_added
            is_mmdd = True

    sensor = AnniversarySensor(hass, name, date_str, is_lunar, is_intercalation, anniv_type, is_mmdd, unique_id)

    async_add_entities([sensor])


def _next_year_date(anniv: date, base_year: int) -> date:
    """2월 29일처럼 해당 연도에 없는 날짜를 안전하게 다음 해로 올림."""
    # 윤년이 아닌 해에 2월 29일이 없으므로 28일로 내림
    if anniv.month == 2 and anniv.day == 29:
        return date(base_year + 1, 2, 28)
    return date(base_year + 1, anniv.month, anniv.day)


class AnniversarySensor(RestoreEntity, SensorEntity):
    """Implementation of an Anniversary sensor."""

    def __init__(self, hass, name, date_str, lunar, intercalation, anniv_type, mmdd, unique_id):
        """Initialize the sensor."""
        self._name = name
        self._date = dt_util.parse_date(date_str)
        self._lunar = lunar
        self._intercalation = intercalation
        self._type = anniv_type
        self._unique_id = unique_id
        self._mmdd = mmdd
        self._state = None
        self._attribute: dict = {}
        self.hass = hass
        self.firmware_version = SW_VERSION
        self.model = MODEL
        self.manufacturer = MANUFACT
        self._update_internal_state(dt_util.utcnow())
        self._cancel_timer = None

    async def async_added_to_hass(self) -> None:
        """HA 재시작 시 직전 상태를 복원해 잠깐 unknown이 되는 현상 방지."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and self._state is None:
            self._state = last_state.state

        # 첫 타이머 시작
        self._cancel_timer = async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval()
        )

    async def async_will_remove_from_hass(self) -> None:
        """엔티티 제거 시 타이머 해제."""
        if self._cancel_timer:
            self._cancel_timer()
        await super().async_will_remove_from_hass()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._name)},
            "name": self._name,
            "sw_version": self.firmware_version,
            "model": self.model,
            "manufacturer": self.manufacturer,
        }

    @property
    def attribution(self):
        return ATTRIBUTION

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        icons = {
            'birth': 'mdi:calendar-star',
            'wedding': 'mdi:calendar-heart',
            'memorial': 'mdi:calendar-clock',
        }
        return icons.get(self._type, 'mdi:calendar-check')

    @property
    def extra_state_attributes(self):
        return self._attribute

    def solar_to_lunar(self, solar_date: date) -> str:
        calendar = KoreanLunarCalendar()
        calendar.setSolarDate(solar_date.year, solar_date.month, solar_date.day)
        return calendar.LunarIsoFormat().replace(' Intercalation', INTERCALATION)

    def lunar_to_solar(self, today: date, this_year: bool) -> date | None:
        lunar_date = self._date
        calendar = KoreanLunarCalendar()
        if this_year or self._mmdd:
            calendar.setLunarDate(today.year, lunar_date.month, lunar_date.day, self._intercalation)
            if calendar.SolarIsoFormat() == '0000-00-00':
                # 해당 연도에 존재하지 않는 음력 날짜 → 하루 앞당겨 보정
                calib = lunar_date - timedelta(1)
                calendar.setLunarDate(today.year, calib.month, calib.day, self._intercalation)
                _LOGGER.warning("Non-existent date correction: %s -> %s", lunar_date, calendar.SolarIsoFormat())
        else:
            calendar.setLunarDate(lunar_date.year, lunar_date.month, lunar_date.day, self._intercalation)
        return dt_util.parse_date(calendar.SolarIsoFormat())

    def lunar_to_solar_early_day(self, today: date) -> date | None:
        """전년도 기준 음력→양력 변환 (d_day 계산용)."""
        lunar_date = self._date
        calendar = KoreanLunarCalendar()
        calendar.setLunarDate(today.year - 1, lunar_date.month, lunar_date.day, self._intercalation)
        if calendar.SolarIsoFormat() == '0000-00-00':
            calib = lunar_date - timedelta(1)
            calendar.setLunarDate(today.year - 1, calib.month, calib.day, self._intercalation)
            _LOGGER.warning("Non-existent date correction: %s -> %s", lunar_date, calendar.SolarIsoFormat())
        return dt_util.parse_date(calendar.SolarIsoFormat())

    def lunar_gapja(self, lunar_date_str: str) -> str:
        intercalation = False
        if '윤달' in lunar_date_str:
            intercalation = True
            lunar_date_str = lunar_date_str.replace(INTERCALATION, '')
        calendar = KoreanLunarCalendar()
        try:
            lunar = dt_util.parse_date(lunar_date_str)
            calendar.setLunarDate(lunar.year, lunar.month, lunar.day, intercalation)
        except Exception:
            try:
                calendar.setLunarDate(
                    int(lunar_date_str[:4]),
                    int(lunar_date_str[5:7]),
                    int(lunar_date_str[8:]),
                    intercalation,
                )
            except Exception:
                _LOGGER.debug("lunar_gapja: 갑자 변환 실패 — %s", lunar_date_str)
                return "-"
        return calendar.getGapJaString()

    def is_past(self, today: date) -> bool:
        if self._lunar:
            anniv = self.lunar_to_solar(today, True)
        else:
            anniv = date(today.year, self._date.month, self._date.day)
        return (anniv - today).days < 0

    def past_days(self, today: date) -> int:
        anniv = self._date if not self._lunar else self.lunar_to_solar(today, False)
        return (today - anniv).days + 1

    def korean_age(self, today: date, upcoming_date_str: str) -> int:
        upcoming_year = dt_util.parse_date(upcoming_date_str).year
        return today.year - self._date.year + 1 + (upcoming_year - today.year)

    def upcoming_count(self, today: date) -> int:
        anniv = self._date if not self._lunar else self.lunar_to_solar(today, False)
        offset = 1 if self.is_past(today) else 0
        return today.year - anniv.year + offset

    def d_day(self, today: date) -> list:
        anniv = self._date

        if self._lunar:
            # 전년도 음력 기준 양력일이 아직 지나지 않았으면 그쪽이 더 가까운 기념일
            anniv_early = self.lunar_to_solar_early_day(today)
            if anniv_early and (anniv_early - today).days >= 0:
                return [(anniv_early - today).days, anniv_early.strftime('%Y-%m-%d')]

        if self.is_past(today):
            if self._lunar:
                ref = date(today.year + 1, today.month, today.day)
                anniv = self.lunar_to_solar(ref, True)
            else:
                anniv = _next_year_date(anniv, today.year)
        else:
            if self._lunar:
                anniv = self.lunar_to_solar(today, True)
            else:
                anniv = date(today.year, anniv.month, anniv.day)

        delta = anniv - today
        return [delta.days, anniv.strftime('%Y-%m-%d')]

    def get_next_interval(self, now=None):
        """자정 직후 업데이트 시각 계산."""
        if now is None:
            now = dt_util.utcnow()
        midnight = dt_util.start_of_local_day(dt_util.as_local(now))
        return midnight + timedelta(seconds=86400)

    def _update_internal_state(self, time_date) -> None:
        today = dt_util.as_local(dt_util.utcnow()).date()
        dday = self.d_day(today)
        self._state = dday[0]

        solar_date = self._date
        if self._lunar:
            solar_date = self.lunar_to_solar(today, False)
            lunar_date = self._date.strftime('%Y-%m-%d')
            if self._intercalation:
                lunar_date += INTERCALATION
        else:
            lunar_date = self.solar_to_lunar(self._date)

        self._attribute = {
            'type': self._type,
            'solar_date': solar_date.strftime('%Y-%m-%d'),
            'lunar_date': lunar_date,
            'lunar_date_gapja': self.lunar_gapja(lunar_date),
            'past_days': '-' if self._mmdd else self.past_days(today),
            'upcoming_count': '-' if self._mmdd else self.upcoming_count(today),
            'upcoming_date': dday[1],
            'korean_age': (
                '-' if self._mmdd or self._type != 'birth'
                else self.korean_age(today, dday[1])
            ),
            'is_lunar': str(self._lunar),
            'is_mmdd': str(self._mmdd),
        }

    @callback
    def point_in_time_listener(self, time_date) -> None:
        """자정마다 상태를 갱신하고 다음 자정 타이머를 등록."""
        self._update_internal_state(time_date)
        self.async_schedule_update_ha_state()
        
        # 기존 타이머가 있다면 취소 후 재등록 (메모리 누수 방지)
        if self._cancel_timer:
            self._cancel_timer()

        self._cancel_timer = async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval()
        )
