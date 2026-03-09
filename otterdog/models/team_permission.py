#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import abc
import dataclasses
from typing import TYPE_CHECKING, Any

from jsonbender import Bender, F  # type: ignore

from otterdog.models import EmbeddedModelObject, FailureType, PatchContext, ValidationContext
from otterdog.utils import (
    IndentingPrinter,
    is_set_and_valid,
    write_patch_object_as_json,
)

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


class StrS(Bender):
    def execute(self, source):
        if not isinstance(source, str):
            raise TypeError(f"Expected string, got {type(source)}")
        return source


class DictS(Bender):
    def __init__(self, value_bender: Bender):
        self.value_bender = value_bender

    def execute(self, source):
        if not isinstance(source, dict):
            raise TypeError(f"Expected dict, got {type(source)}")

        result = {}
        for key, value in source.items():
            result[key] = self.value_bender.execute(value)
        return result


@dataclasses.dataclass
class TeamPermissions(EmbeddedModelObject, abc.ABC):
    """
    Represents a Team Permission on a Repository.
    """

    perms: dict[str, str] = dataclasses.field(default_factory=dict)  # Team_name: permission

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if is_set_and_valid(self.perms):
            allowed = {
                "pull",
                "triage",
                "push",
                "maintain",
                "admin",
                "READ",
                "WRITE",
                "MAINTAIN",
                "TRIAGE",
                "ADMIN",
            }

            for team, perm in self.perms.items():
                if perm not in allowed:
                    context.add_failure(
                        FailureType.ERROR,
                        f"invalid permission '{perm}' "
                        f"for team '{team}', allowed values are "
                        f"('read/pull' | 'triage' | 'write/push' | 'maintain' | 'admin').",
                    )

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        def transform_perm(d: dict[str, str]) -> dict[str, str]:
            to_provider = {
                "READ": "pull",
                "TRIAGE": "triage",
                "WRITE": "push",
                "MAINTAIN": "maintain",
                "ADMIN": "admin",
            }
            return {team: to_provider[perm] for team, perm in d.items()}

        mapping.update({"perms": DictS(StrS()) >> F(transform_perm)})
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = await super().get_mapping_to_provider(org_id, data, provider)
        return mapping

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return None

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        context: PatchContext,
        extend: bool,
        default_object: EmbeddedModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)
        write_patch_object_as_json(patch, printer, False)
        printer.level_down()
        printer.println("},")
