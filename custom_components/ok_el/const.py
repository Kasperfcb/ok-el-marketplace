"""Constants for the unofficial OK El integration."""
from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "ok_el"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
PLATFORMS = [Platform.SENSOR]
UPDATE_INTERVAL = timedelta(hours=6)
