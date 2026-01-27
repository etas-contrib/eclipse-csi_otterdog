#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchType,
    ModelObject,
    ValidationContext,
)
from otterdog.utils import (
    unwrap,
    expect_type,
    is_set_and_valid,
)

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class TeamPermission(ModelObject):
    """
    Represents a Team Permission on a Repository.
    """

    name: str = dataclasses.field(metadata={"key": True})
    permission: str

    @property
    def model_object_name(self) -> str:
        return "teampermission"
    
    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_team_permission}"
    
    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if is_set_and_valid(self.permission):
            if self._permission not in {"READ", "WRITE", "MAINTAIN", "ADMIN"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'permission' of value '{self.permission}', "
                    f"while only values ('none' | 'read' | 'triage' | 'write' | 'maintain' | 'admin') are allowed.",
                )

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = await super().get_mapping_to_provider(org_id, data, provider)
        
        if "name" in data:
            mapping.pop("name")

        return mapping


    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[TeamPermission],
        org_id: str,
        provider: GitHubProvider
    ) -> None:
        from .repository import Repository

        repository = expect_type(patch.parent_object, Repository)

        match patch.patch_type:
            case LivePatchType.ADD:
                await provider.add_team_permission(
                    org_id,
                    repository.name,
                    unwrap(patch.expected_object).name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )
            
            case LivePatchType.REMOVE:
                await provider.delete_team_permission(
                    org_id,
                    repository.name,
                    unwrap(patch.current_object).name,
                )

            case LivePatchType.CHANGE:
                await provider.update_team_permission(
                    org_id,
                    repository.name,
                    unwrap(patch.current_object).name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )
