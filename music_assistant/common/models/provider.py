"""Models for providers and plugins in the MA ecosystem."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from mashumaro.mixins.orjson import DataClassORJSONMixin

from music_assistant.common.helpers.json import load_json_file

from .enums import MediaType, ProviderFeature, ProviderType


@dataclass
class ProviderManifest(DataClassORJSONMixin):
    """ProviderManifest, details of a provider."""

    type: ProviderType
    domain: str
    name: str
    description: str
    codeowners: list[str]

    # optional params

    # requirements: list of (pip style) python packages required for this provider
    requirements: list[str] = field(default_factory=list)
    # documentation: link/url to documentation.
    documentation: str | None = None
    # multi_instance: whether multiple instances of the same provider are allowed/possible
    multi_instance: bool = False
    # builtin: whether this provider is a system/builtin provider, loaded by default
    builtin: bool = False
    # allow_disable: whether this provider can be disabled (used with builtin)
    allow_disable: bool = True
    # depends_on: depends on another provider to function
    depends_on: str | None = None
    # icon: name of the material design icon (https://pictogrammers.com/library/mdi)
    icon: str | None = None
    # icon_svg: svg icon (full xml string)
    # if this attribute is omitted and an icon.svg is found in the provider
    # folder, the file contents will be read instead.
    icon_svg: str | None = None
    # icon_svg_dark: optional separate dark svg icon (full xml string)
    # if this attribute is omitted and an icon_dark.svg is found in the provider
    # folder, the file contents will be read instead.
    icon_svg_dark: str | None = None
    # mdns_discovery: list of mdns types to discover
    mdns_discovery: list[str] | None = None

    @classmethod
    async def parse(cls, manifest_file: str) -> ProviderManifest:
        """Parse ProviderManifest from file."""
        return await load_json_file(manifest_file, ProviderManifest)


@dataclass
class ProviderInstance(DataClassORJSONMixin):
    """Provider instance details when a provider is serialized over the api."""

    type: ProviderType
    domain: str
    name: str
    instance_id: str
    lookup_key: str
    supported_features: list[ProviderFeature]
    available: bool
    icon: str | None = None
    is_streaming_provider: bool | None = None  # music providers only


@dataclass
class SyncTask:
    """Description of a Sync task/job of a musicprovider."""

    provider_domain: str
    provider_instance: str
    media_types: tuple[MediaType, ...]
    task: asyncio.Task[None] | None

    def to_dict(self) -> dict[str, Any]:
        """Return SyncTask as (serializable) dict."""
        # ruff: noqa:ARG002
        return {
            "provider_domain": self.provider_domain,
            "provider_instance": self.provider_instance,
            "media_types": [x.value for x in self.media_types],
        }
