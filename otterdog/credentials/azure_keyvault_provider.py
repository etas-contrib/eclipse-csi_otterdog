#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from typing import Any

from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient

from otterdog.credentials import CredentialProvider, Credentials
from otterdog.logging import get_logger

_logger = get_logger(__name__)


class AzureKeyVaultProvider(CredentialProvider):
    def __init__(self, vault_name: str, tenant_id: str, client_id: str, client_secret: str):

        _logger.debug("unlocking Azure Key Vault")
        self._vault_url = f"https://{vault_name}.vault.azure.net"

        self._credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

        self._client = SecretClient(
            vault_url=self._vault_url,
            credential=self._credential,
        )

    @property
    def vault_url(self) -> str:
        return self._vault_url

    def get_credentials(self, org_name: str, data: dict[str, Any], only_token: bool = False) -> Credentials:
        token = self.get_secret(data["token_secret_name"])

        if only_token:
            # Credentials(token, None)
            return Credentials(None, None, None, token)

        username = self.get_secret(data["username_secret_name"])

        # Credentials(token, username)
        return Credentials(username, None, None, token)

    def get_secret(self, name: str) -> str:
        secret = self._client.get_secret(name)
        value = secret.value

        if value is None:
            raise ValueError(f"Secret '{name}' has no value in Azure Key Vault")

        return value

    def __repr__(self):
        return f"AzureKeyVault(vault url='{self._vault_url}')"
