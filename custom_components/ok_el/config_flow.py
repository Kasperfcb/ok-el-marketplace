"""UI-based configuration of an OK account, no manual agreement number."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .client import OKAPIError, OKClient
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .dates import COPENHAGEN, month_window


class WrongCredentials(Exception):
    """Min OK rejected the credentials."""


class AgreementDiscoveryError(Exception):
    """The login did not yield exactly one agreement."""


def verify_account(email: str, password: str) -> None:
    """Run in HA's executor. Do not return IDs or persist cookies."""
    client = OKClient()
    try:
        client.login(email, password)
    except OKAPIError as exc:
        if "Login blev ikke godkendt" in str(exc):
            raise WrongCredentials from exc
        raise

    candidates = client.discover_agreement_numbers()
    if len(candidates) != 1:
        raise AgreementDiscoveryError

    today = datetime.now(COPENHAGEN).date()
    start, end = month_window(today.year, today.month)
    rows = client.get_data(
        candidates[0], period="DAY", start=start, end=end, display_type=0
    )
    if not isinstance(rows, list):
        raise OKAPIError("Uventet svar fra OK's forbrugs-API")


def _account_uid(email: str) -> str:
    """Stable account identity without exposing an email in unique IDs."""
    return "account_" + sha256(email.strip().casefold().encode("utf-8")).hexdigest()


PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
USER_SCHEMA = vol.Schema({
    vol.Required(CONF_EMAIL): str,
    vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
})
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR})


class OKElConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Validate credentials before creating a HA config entry."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            try:
                await self.hass.async_add_executor_job(verify_account, email, password)
            except WrongCredentials:
                errors["base"] = "invalid_auth"
            except AgreementDiscoveryError:
                errors["base"] = "agreement_not_found"
            except OKAPIError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(_account_uid(email))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Min OK El",
                    data={CONF_EMAIL: email, CONF_PASSWORD: password},
                )
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict) -> ConfigFlowResult:
        """Show a password field when OK rejects saved credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            try:
                await self.hass.async_add_executor_job(
                    verify_account, entry.data[CONF_EMAIL], password
                )
            except WrongCredentials:
                errors["base"] = "invalid_auth"
            except AgreementDiscoveryError:
                errors["base"] = "agreement_not_found"
            except OKAPIError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(_account_uid(entry.data[CONF_EMAIL]))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: password}
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors,
        )
