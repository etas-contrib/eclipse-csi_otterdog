#  *******************************************************************************
#  Copyright (c) 2023-2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import Any

from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from otterdog.credentials import CredentialPlaceHolders, CredentialProvider, Credentials
from otterdog.logging import get_logger

_logger = get_logger(__name__)


class AzureKeyVaultProvider(CredentialProvider):
    """
    CredentialProvider backed by Azure Key Vault secrets.

    Expected `data` keys in otterdog config:
      - token_secret_name              (mandatory)
      - username_secret_name           (optional, unless only_token=False)
    """

    def __init__(
        self,
        vault_name: str,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        enable_cache: bool = True,
    ):
        self._vault_url = f"https://{vault_name}.vault.azure.net"

        _logger.debug(
            "initializing Azure Key Vault provider (vault=%s, cache=%s)",
            self._vault_url,
            enable_cache,
        )

        # ------------------------------------------------------------------
        # Authentication
        # ------------------------------------------------------------------
        if client_secret:
            self._client = SecretClient(
                vault_url=self._vault_url,
                credential=ClientSecretCredential(
                    tenant_id=tenant_id or "",
                    client_id=client_id or "",
                    client_secret=client_secret,
                ),
            )
        else:
            self._client = SecretClient(
                vault_url=self._vault_url,
                credential=DefaultAzureCredential(),
            )

        # ------------------------------------------------------------------
        # Cache
        # ------------------------------------------------------------------
        self._enable_cache = enable_cache
        self._cache: dict[str, str] = {}

    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------

    @property
    def vault_url(self) -> str:
        return self._vault_url

    def get_credentials(
        self,
        placeholders: CredentialPlaceHolders,
        data: dict[str, Any],
        only_token: bool = False,
    ) -> Credentials:
        """
        Resolve credentials for a GitHub organization from Azure Key Vault.
        """

        self._validate_data(data, only_token)

        token = self._get_secret(
            name=data["token_secret_name"],
            org_name=placeholders["org_name"],
        )

        if only_token:
            return Credentials(None, None, None, token)

        username = self._get_secret(
            name=data["username_secret_name"],
            org_name=placeholders["org_name"],
        )

        return Credentials(username, None, None, token)

    def get_secret(self, data: str) -> str:
        """
        Otterdog secret resolution entrypoint.
        """
        return self._get_secret(name=data, org_name="<unknown>")

    # ----------------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------------

    def _get_secret(self, name: str, org_name: str) -> str:
        if self._enable_cache and name in self._cache:
            return self._cache[name]

        try:
            secret = self._client.get_secret(name)
            value = secret.value
        except Exception as ex:
            raise RuntimeError(
                "Failed to retrieve secret from Azure Key Vault.\n"
                f"  vault_url : {self._vault_url}\n"
                f"  secret    : {name}\n"
                f"  org       : {org_name}\n"
                "Hints:\n"
                "  - Ensure the Azure identity has 'get' permission for secrets.\n"
                "  - Verify the secret name and vault configuration.\n"
                f"Original error: {ex!s}"
            ) from ex

        if value is None:
            raise ValueError(
                "Azure Key Vault returned an empty secret value.\n"
                f"  vault_url : {self._vault_url}\n"
                f"  secret    : {name}\n"
                f"  org       : {org_name}"
            )

        if self._enable_cache:
            self._cache[name] = value

        return value

    @staticmethod
    def _validate_data(data: dict[str, Any], only_token: bool) -> None:
        required_keys = ["token_secret_name"]
        if not only_token:
            required_keys.append("username_secret_name")

        missing = [key for key in required_keys if key not in data]
        if missing:
            raise ValueError(f"AzureKeyVaultProvider: missing required configuration keys: {missing}")

    def __repr__(self) -> str:
        return f"AzureKeyVaultProvider(vault_url='{self._vault_url}')"
