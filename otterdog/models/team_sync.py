#  *******************************************************************************
#  Copyright (c) 2023-2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


import abc
import dataclasses
from typing import Any

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import LivePatch, LivePatchType, ModelObject, ValidationContext
from otterdog.providers.github import GitHubProvider
from otterdog.utils import expect_type, unwrap


@dataclasses.dataclass
class TeamSync(ModelObject, abc.ABC):
    """
    Represents a team sync to an IdP provider
    """
    name: str = dataclasses.field(metadata={"key": True})
    description: str
    id: str

    @property
    def model_object_name(self) -> str:
        return "team_sync"
    
    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_team_sync}"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        pass

