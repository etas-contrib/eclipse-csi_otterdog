#  *******************************************************************************
#  Copyright (c) 2023-2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


from __future__ import annotations

import base64
from typing import Any, Dict, Optional
from pathlib import Path

from kubernetes import client, config
from otterdog.credentials import CredentialProvider, Credentials
from otterdog.logging import get_logger

_logger = get_logger(__name__)


class KubernetesSecretProvider(CredentialProvider):
    """
    CredentialProvider backed by Kubernetes Secrets via the Kubernetes API.

    Expected `data` keys in otterdog config:
      - token_secret_name              (mandatory)
      - username_secret_name           (optional, unless only_token=False)
      - namespace                      (optional, defaults to 'default')
    """

    def __init__(
        self,
        enable_cache: bool = True,
    ):
        _logger.debug(
            "initializing Kubernetes Secret provider (cache=%s)",
            enable_cache,
        )

        # ------------------------------------------------------------------
        # Kubernetes API initialization
        # ------------------------------------------------------------------
        try:
            # Loads in-cluster configuration using the service account token
            config.load_incluster_config()
            self._v1 = client.CoreV1Api()
        except Exception as ex:
            raise RuntimeError(
                "Failed to initialize Kubernetes in-cluster configuration.\n"
                "Hints:\n"
                "  - Ensure the Pod is running inside Kubernetes.\n"
                "  - Ensure the ServiceAccount token is mounted.\n"
                f"Original error: {ex!s}"
            ) from ex

        # ------------------------------------------------------------------
        # Cache
        # ------------------------------------------------------------------
        self._enable_cache = enable_cache
        self._cache: Dict[str, str] = {}

    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------

    def get_credentials(
        self,
        org_name: str,
        data: dict[str, Any],
        only_token: bool = False,
    ) -> Credentials:
        """
        Resolve credentials for a GitHub organization from Kubernetes Secrets.
        """

        self._validate_data(data, only_token)

        namespace = data.get("namespace") or self._get_current_namespace()

        token = self._get_secret(
            name=data["token_secret_name"],
            namespace=namespace,
            org_name=org_name,
        )

        if only_token:
            return Credentials(None, token, None, None)

        username = self._get_secret(
            name=data["username_secret_name"],
            namespace=namespace,
            org_name=org_name,
        )

        return Credentials(username, token, None, None)

    def get_secret(self, data: str) -> str:
        """
        Otterdog secret resolution entrypoint.
        """
        namespace = self._get_current_namespace()

        # Default namespace for standalone secret resolution
        return self._get_secret(name=data, namespace=namespace, org_name="<unknown>")

    # ----------------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------------

    def _get_secret(self, name: str, namespace: str, org_name: str) -> str:
        cache_key = f"{namespace}:{name}"

        if self._enable_cache and cache_key in self._cache:
            return self._cache[cache_key]

        try:
            secret = self._v1.read_namespaced_secret(
                name=name,
                namespace=namespace,
            )
        except Exception as ex:
            raise RuntimeError(
                "Failed to retrieve secret from Kubernetes.\n"
                f"  namespace : {namespace}\n"
                f"  secret    : {name}\n"
                f"  org       : {org_name}\n"
                "Hints:\n"
                "  - Ensure the ServiceAccount has 'get' permission for secrets.\n"
                "  - Verify the secret name and namespace.\n"
                f"Original error: {ex!s}"
            ) from ex

        if not secret.data or name not in secret.data:
            raise ValueError(
                "Kubernetes returned an empty or missing secret value.\n"
                f"  namespace : {namespace}\n"
                f"  secret    : {name}\n"
                f"  org       : {org_name}"
            )

        try:
            encoded = secret.data[name]
            value = base64.b64decode(encoded).decode("utf-8")
        except Exception as ex:
            raise RuntimeError(
                "Failed to decode Base64 secret value.\n"
                f"  namespace : {namespace}\n"
                f"  secret    : {name}\n"
                f"  org       : {org_name}\n"
                f"Original error: {ex!s}"
            ) from ex

        if self._enable_cache:
            self._cache[cache_key] = value

        return value

    def _get_current_namespace(self) -> str:
            """
            Determine the current namespace when running inside a Kubernetes pod.
            """
            namespace_file = Path(
                "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
            )
            try:
                return namespace_file.read_text().strip()
            except Exception:
                return "default"

    @staticmethod
    def _validate_data(data: dict[str, Any], only_token: bool) -> None:
        required_keys = ["token_secret_name"]
        if not only_token:
            required_keys.append("username_secret_name")

        missing = [key for key in required_keys if key not in data]
        if missing:
            raise ValueError(
                "KubernetesSecretProvider: missing required configuration keys: "
                f"{missing}"
            )

    def __repr__(self) -> str:
        return "KubernetesSecretProvider()"
