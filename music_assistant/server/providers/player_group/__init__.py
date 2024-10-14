"""
Sync Group Player provider.

This is more like a "virtual" player provider,
allowing the user to create 'presets' of players to sync together (of the same type).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from time import time
from typing import TYPE_CHECKING, Final, cast

import shortuuid
from aiohttp import web

from music_assistant.common.models.config_entries import (
    BASE_PLAYER_CONFIG_ENTRIES,
    CONF_ENTRY_CROSSFADE,
    CONF_ENTRY_CROSSFADE_DURATION,
    CONF_ENTRY_FLOW_MODE_ENFORCED,
    CONF_ENTRY_PLAYER_ICON_GROUP,
    ConfigEntry,
    ConfigValueOption,
    ConfigValueType,
    PlayerConfig,
    create_sample_rates_config_entry,
)
from music_assistant.common.models.enums import (
    ConfigEntryType,
    ContentType,
    EventType,
    MediaType,
    PlayerFeature,
    PlayerState,
    PlayerType,
    ProviderFeature,
)
from music_assistant.common.models.errors import (
    PlayerUnavailableError,
    ProviderUnavailableError,
    UnsupportedFeaturedException,
)
from music_assistant.common.models.event import MassEvent
from music_assistant.common.models.media_items import AudioFormat
from music_assistant.common.models.player import DeviceInfo, Player, PlayerMedia
from music_assistant.constants import (
    CONF_CROSSFADE,
    CONF_CROSSFADE_DURATION,
    CONF_ENABLE_ICY_METADATA,
    CONF_ENFORCE_MP3,
    CONF_FLOW_MODE,
    CONF_GROUP_MEMBERS,
    CONF_HTTP_PROFILE,
    CONF_SAMPLE_RATES,
)
from music_assistant.server.controllers.streams import DEFAULT_STREAM_HEADERS
from music_assistant.server.helpers.ffmpeg import get_ffmpeg_stream
from music_assistant.server.helpers.util import TaskManager
from music_assistant.server.models.player_provider import PlayerProvider

from .ugp_stream import UGP_FORMAT, UGPStream

if TYPE_CHECKING:
    from collections.abc import Iterable

    from music_assistant.common.models.config_entries import ProviderConfig
    from music_assistant.common.models.provider import ProviderManifest
    from music_assistant.server import MusicAssistant
    from music_assistant.server.models import ProviderInstanceType


# ruff: noqa: ARG002

UNIVERSAL_PREFIX: Final[str] = "ugp_"
SYNCGROUP_PREFIX: Final[str] = "syncgroup_"
GROUP_TYPE_UNIVERSAL: Final[str] = "universal"
CONF_GROUP_TYPE: Final[str] = "group_type"
CONF_ENTRY_GROUP_TYPE = ConfigEntry(
    key=CONF_GROUP_TYPE,
    type=ConfigEntryType.STRING,
    label="Group type",
    default_value="universal",
    hidden=True,
    required=True,
)
CONF_ENTRY_GROUP_MEMBERS = ConfigEntry(
    key=CONF_GROUP_MEMBERS,
    type=ConfigEntryType.STRING,
    label="Group members",
    default_value=[],
    description="Select all players you want to be part of this group",
    multi_value=True,
    required=True,
)
CONF_ENTRY_SAMPLE_RATES_UGP = create_sample_rates_config_entry(44100, 16, 44100, 16, True)
CONFIG_ENTRY_UGP_NOTE = ConfigEntry(
    key="ugp_note",
    type=ConfigEntryType.LABEL,
    label="Please note that although the Universal Group "
    "allows you to group any player, it will not enable audio sync "
    "between players of different ecosystems. It is advised to always use native "
    "player groups or sync groups when available for your player type(s) and use "
    "the Universal Group only to group players of different ecosystems.",
    required=False,
)


async def setup(
    mass: MusicAssistant, manifest: ProviderManifest, config: ProviderConfig
) -> ProviderInstanceType:
    """Initialize provider(instance) with given configuration."""
    return PlayerGroupProvider(mass, manifest, config)


async def get_config_entries(
    mass: MusicAssistant,  # noqa: ARG001
    instance_id: str | None = None,  # noqa: ARG001
    action: str | None = None,  # noqa: ARG001
    values: dict[str, ConfigValueType] | None = None,  # noqa: ARG001
) -> tuple[ConfigEntry, ...]:
    """
    Return Config entries to setup this provider.

    instance_id: id of an existing provider instance (None if new instance setup).
    action: [optional] action key called from config entries UI.
    values: the (intermediate) raw values for config entries sent with the action.
    """
    # nothing to configure (for now)
    return ()


class PlayerGroupProvider(PlayerProvider):
    """Base/builtin provider for creating (permanent) player groups."""

    def __init__(
        self, mass: MusicAssistant, manifest: ProviderManifest, config: ProviderConfig
    ) -> None:
        """Initialize MusicProvider."""
        super().__init__(mass, manifest, config)
        self.ugp_streams: dict[str, UGPStream] = {}
        self._on_unload: list[Callable[[], None]] = [
            self.mass.register_api_command("player_group/create", self.create_group),
        ]

    async def loaded_in_mass(self) -> None:
        """Call after the provider has been loaded."""
        # temp: migrate old config entries
        # remove this after MA 2.4 release
        for player_config in await self.mass.config.get_player_configs():
            if player_config.provider == self.instance_id:
                # already migrated
                continue
            # migrate old syncgroup players to this provider
            if player_config.player_id.startswith(SYNCGROUP_PREFIX):
                self.mass.config.set_raw_player_config_value(
                    player_config.player_id, CONF_GROUP_TYPE, player_config.provider
                )
                player_config.provider = self.instance_id
                self.mass.config.set_raw_player_config_value(
                    player_config.player_id, "provider", self.instance_id
                )
            # migrate old UGP players to this provider
            elif player_config.player_id.startswith(UNIVERSAL_PREFIX):
                self.mass.config.set_raw_player_config_value(
                    player_config.player_id, CONF_GROUP_TYPE, "universal"
                )
                player_config.provider = self.instance_id
                self.mass.config.set_raw_player_config_value(
                    player_config.player_id, "provider", self.instance_id
                )

        await self._register_all_players()
        # listen for player added events so we can catch late joiners
        # (because a group depends on its childs to be available)
        self._on_unload.append(
            self.mass.subscribe(self._on_mass_player_added_event, EventType.PLAYER_ADDED)
        )

    async def unload(self) -> None:
        """
        Handle unload/close of the provider.

        Called when provider is deregistered (e.g. MA exiting or config reloading).
        """
        for unload_cb in self._on_unload:
            unload_cb()

    async def get_player_config_entries(self, player_id: str) -> tuple[ConfigEntry]:
        """Return all (provider/player specific) Config Entries for the given player (if any)."""
        # default entries for player groups
        base_entries = (
            *BASE_PLAYER_CONFIG_ENTRIES,
            CONF_ENTRY_PLAYER_ICON_GROUP,
            CONF_ENTRY_GROUP_TYPE,
            CONF_ENTRY_GROUP_MEMBERS,
        )
        # group type is static and can not be changed. we just grab the existing, stored value
        group_type: str = self.mass.config.get_raw_player_config_value(
            player_id, CONF_GROUP_TYPE, GROUP_TYPE_UNIVERSAL
        )
        # handle config entries for universal group players
        if group_type == GROUP_TYPE_UNIVERSAL:
            group_members = CONF_ENTRY_GROUP_MEMBERS
            group_members.options = tuple(
                ConfigValueOption(x.display_name, x.player_id)
                for x in self.mass.players.all(True, False)
                if not x.player_id.startswith(UNIVERSAL_PREFIX)
            )
            return (
                *base_entries,
                group_members,
                CONFIG_ENTRY_UGP_NOTE,
                CONF_ENTRY_CROSSFADE,
                CONF_ENTRY_CROSSFADE_DURATION,
                CONF_ENTRY_SAMPLE_RATES_UGP,
                CONF_ENTRY_FLOW_MODE_ENFORCED,
            )
        # handle config entries for syncgroup players
        group_members = CONF_ENTRY_GROUP_MEMBERS
        group_members.options = tuple(
            ConfigValueOption(x.display_name, x.player_id)
            for x in self.mass.players.all(True, False)
            if x.provider != self.instance_id
            and (player_prov := self.mass.get_provider(x.provider))
            and ProviderFeature.SYNC_PLAYERS in player_prov.supported_features
        )

        # grab additional details from one of the provider's players
        if not (player_provider := self.mass.get_provider(group_type)):
            return base_entries  # guard
        if TYPE_CHECKING:
            player_provider = cast(PlayerProvider, player_provider)
        assert player_provider.lookup_key != self.lookup_key
        if not (child_player := next((x for x in player_provider.players), None)):
            return base_entries  # guard

        # combine base group entries with (base) player entries for this player type
        allowed_conf_entries = (
            CONF_HTTP_PROFILE,
            CONF_ENABLE_ICY_METADATA,
            CONF_CROSSFADE,
            CONF_CROSSFADE_DURATION,
            CONF_ENFORCE_MP3,
            CONF_FLOW_MODE,
            CONF_SAMPLE_RATES,
        )
        child_config_entries = await player_provider.get_player_config_entries(
            child_player.player_id
        )
        return (
            *base_entries,
            group_members,
            *(entry for entry in child_config_entries if entry.key in allowed_conf_entries),
        )

    def on_player_config_changed(self, config: PlayerConfig, changed_keys: set[str]) -> None:
        """Call (by config manager) when the configuration of a player changes."""
        if "enabled" in changed_keys and not config.enabled:
            # edge case: ensure that the player is powered off if the player gets disabled
            self.mass.create_task(self.cmd_power(config.player_id, False))
        if f"values/{CONF_GROUP_MEMBERS}" in changed_keys:
            members = config.get_value(CONF_GROUP_MEMBERS)
            # ensure we filter invalid members
            members = self._filter_members(config.get_value(CONF_GROUP_TYPE), members)
            self.mass.config.set_raw_player_config_value(
                config.player_id, CONF_GROUP_MEMBERS, members
            )
            if player := self.mass.players.get(config.player_id):
                player.group_childs = members
                self.mass.players.update(config.player_id)

    def on_player_config_removed(self, player_id: str) -> None:
        """Call (by config manager) when the configuration of a player is removed."""
        if not (group_player := self.mass.players.get(player_id)):
            return
        if group_player.powered:
            # edge case: the group player is powered and being removed
            for member in self.mass.players.iter_group_members(group_player, only_powered=True):
                member.active_group = None
                if member.state == PlayerState.IDLE:
                    continue
                if member.synced_to:
                    continue
                self.mass.create_task(
                    self.mass.players.cmd_stop(member.player_id, skip_redirect=True)
                )
            self.mass.players.remove(group_player.player_id, False)

    async def cmd_stop(self, player_id: str) -> None:
        """Send STOP command to given player."""
        group_player = self.mass.players.get(player_id)
        if player_id.startswith(SYNCGROUP_PREFIX):
            # syncgroup: forward command to sync leader
            if sync_leader := self._get_sync_leader(group_player):
                await self.mass.players.cmd_stop(sync_leader.player_id, skip_redirect=True)
        else:
            # ugp: forward command to all active members
            async with TaskManager(self.mass) as tg:
                for member in self.mass.players.iter_group_members(group_player, active_only=True):
                    if member.state not in (PlayerState.PAUSED, PlayerState.PLAYING):
                        continue
                    tg.create_task(self.mass.players.cmd_stop(member.player_id, skip_redirect=True))
            # abort the stream session
            if (stream := self.ugp_streams.pop(player_id, None)) and not stream.done:
                await stream.stop()
        # set state optimistically
        group_player.state = PlayerState.IDLE
        self.mass.players.update(player_id)

    async def cmd_play(self, player_id: str) -> None:
        """Send PLAY command to given player."""
        group_player = self.mass.players.get(player_id)
        if not player_id.startswith(SYNCGROUP_PREFIX):
            # this shouldn't happen, but just in case
            raise UnsupportedFeaturedException("Command is not supported for UGP players")
        # forward command to sync leader
        if sync_leader := self._get_sync_leader(group_player):
            await self.mass.players.cmd_play(sync_leader.player_id, skip_redirect=True)

    async def cmd_pause(self, player_id: str) -> None:
        """Send PAUSE command to given player."""
        group_player = self.mass.players.get(player_id)
        if not player_id.startswith(SYNCGROUP_PREFIX):
            raise UnsupportedFeaturedException("Command is not supported for UGP players")
        # forward command to sync leader
        if sync_leader := self._get_sync_leader(group_player):
            await self.mass.players.cmd_pause(sync_leader.player_id, skip_redirect=True)

    async def cmd_power(self, player_id: str, powered: bool) -> None:
        """Handle POWER command to group player."""
        group_player = self.mass.players.get(player_id, raise_unavailable=True)
        if TYPE_CHECKING:
            group_player = cast(Player, group_player)

        # always stop at power off
        if not powered and group_player.state in (PlayerState.PLAYING, PlayerState.PAUSED):
            await self.cmd_stop(group_player.player_id)

        async with TaskManager(self.mass) as tg:
            if powered:
                # handle TURN_ON of the group player by turning on all members
                for member in self.mass.players.iter_group_members(
                    group_player, only_powered=False, active_only=False
                ):
                    if (
                        member.state in (PlayerState.PLAYING, PlayerState.PAUSED)
                        and member.active_source != group_player.active_source
                    ):
                        # stop playing existing content on member if we start the group player
                        tg.create_task(
                            self.mass.players.cmd_stop(member.player_id, skip_redirect=True)
                        )
                    if not member.powered:
                        tg.create_task(
                            self.mass.players.cmd_power(member.player_id, True, skip_redirect=True)
                        )
                    # set active source to group player if the group (is going to be) powered
                    member.active_group = group_player.player_id
                    member.active_source = group_player.active_source
            else:
                # handle TURN_OFF of the group player by turning off all members
                for member in self.mass.players.iter_group_members(
                    group_player, only_powered=True, active_only=True
                ):
                    # reset active group on player when the group is turned off
                    member.active_group = None
                    member.active_source = None
                    # handle TURN_OFF of the group player by turning off all members
                    if member.powered:
                        tg.create_task(
                            self.mass.players.cmd_power(member.player_id, False, skip_redirect=True)
                        )
        if powered and player_id.startswith(SYNCGROUP_PREFIX):
            await self._sync_syncgroup(group_player)
        # optimistically set the group state
        group_player.powered = powered
        self.mass.players.update(group_player.player_id)

    async def cmd_volume_set(self, player_id: str, volume_level: int) -> None:
        """Send VOLUME_SET command to given player."""
        # group volume is already handled in the player manager

    async def play_media(
        self,
        player_id: str,
        media: PlayerMedia,
    ) -> None:
        """Handle PLAY MEDIA on given player."""
        group_player = self.mass.players.get(player_id)
        # power on (or resync) if needed
        if group_player.powered and player_id.startswith(SYNCGROUP_PREFIX):
            await self._sync_syncgroup(group_player)
        else:
            await self.cmd_power(player_id, True)

        # set the state optimistically
        group_player.current_media = media
        group_player.elapsed_time = 0
        group_player.elapsed_time_last_updated = time() - 1
        group_player.state = PlayerState.PLAYING
        self.mass.players.update(player_id)

        # handle play_media for sync group
        if player_id.startswith(SYNCGROUP_PREFIX):
            # simply forward the command to the sync leader
            if sync_leader := self._select_sync_leader(group_player):
                await self.mass.players.play_media(
                    sync_leader.player_id, media=media, skip_redirect=True
                )
            return

        # handle play_media for UGP group
        if (existing := self.ugp_streams.pop(player_id, None)) and not existing.done:
            # stop any existing stream first
            await existing.stop()

        # select audio source
        if media.media_type == MediaType.ANNOUNCEMENT:
            # special case: stream announcement
            audio_source = self.mass.streams.get_announcement_stream(
                media.custom_data["url"],
                output_format=UGP_FORMAT,
                use_pre_announce=media.custom_data["use_pre_announce"],
            )
        elif media.queue_id and media.queue_item_id:
            # regular queue stream request
            audio_source = self.mass.streams.get_flow_stream(
                queue=self.mass.player_queues.get(media.queue_id),
                start_queue_item=self.mass.player_queues.get_item(
                    media.queue_id, media.queue_item_id
                ),
                pcm_format=UGP_FORMAT,
            )
        else:
            # assume url or some other direct path
            # NOTE: this will fail if its an uri not playable by ffmpeg
            audio_source = get_ffmpeg_stream(
                audio_input=media.uri,
                input_format=AudioFormat(ContentType.try_parse(media.uri)),
                output_format=UGP_FORMAT,
            )

        # start the stream task
        self.ugp_streams[player_id] = UGPStream(audio_source=audio_source, audio_format=UGP_FORMAT)
        base_url = f"{self.mass.streams.base_url}/ugp/{player_id}.aac"

        # forward to downstream play_media commands
        async with TaskManager(self.mass) as tg:
            for member in self.mass.players.iter_group_members(
                group_player, only_powered=True, active_only=True
            ):
                tg.create_task(
                    self.mass.players.play_media(
                        member.player_id,
                        media=PlayerMedia(
                            uri=f"{base_url}?player_id={member.player_id}",
                            media_type=MediaType.FLOW_STREAM,
                            title=group_player.display_name,
                            queue_id=group_player.player_id,
                        ),
                        skip_redirect=True,
                    )
                )

    async def enqueue_next_media(self, player_id: str, media: PlayerMedia) -> None:
        """Handle enqueuing of a next media item on the player."""
        group_player = self.mass.players.get(player_id, True)
        if not player_id.startswith(SYNCGROUP_PREFIX):
            # this shouldn't happen, but just in case
            raise UnsupportedFeaturedException("Command is not supported for UGP players")
        if sync_leader := self._get_sync_leader(group_player):
            await self.mass.players.enqueue_next_media(
                sync_leader.player_id,
                media=media,
            )

    async def poll_player(self, player_id: str) -> None:
        """Poll player for state updates.

        This is called by the Player Manager;
        if 'needs_poll' is set to True in the player object.
        """
        if group_player := self.mass.players.get(player_id):
            self._update_attributes(group_player)

    async def create_group(self, group_type: str, name: str, members: list[str]) -> Player:
        """Create new Group Player."""
        # perform basic checks
        if group_type == GROUP_TYPE_UNIVERSAL:
            prefix = UNIVERSAL_PREFIX
        else:
            prefix = SYNCGROUP_PREFIX
            if (player_prov := self.mass.get_provider(group_type)) is None:
                msg = f"Provider {group_type} is not available!"
                raise ProviderUnavailableError(msg)
            if ProviderFeature.SYNC_PLAYERS not in player_prov.supported_features:
                msg = f"Provider {player_prov.name} does not support creating groups"
                raise UnsupportedFeaturedException(msg)

        new_group_id = f"{prefix}{shortuuid.random(8).lower()}"
        # cleanup list, just in case the frontend sends some garbage
        members = self._filter_members(group_type, members)
        # create default config with the user chosen name
        self.mass.config.create_default_player_config(
            new_group_id,
            player_prov.instance_id,
            name=name,
            enabled=True,
            values={CONF_GROUP_MEMBERS: members, CONF_GROUP_TYPE: group_type},
        )
        return self._register_group_player(
            group_player_id=new_group_id, group_type=group_type, name=name, members=members
        )

    async def _register_all_players(self) -> None:
        """Register all (virtual/fake) group players in the Player controller."""
        player_configs = await self.mass.config.get_player_configs(
            self.instance_id, include_values=True
        )
        for player_config in player_configs:
            if self.mass.players.get(player_config.player_id):
                continue  # already registered
            members = player_config.get_value(CONF_GROUP_MEMBERS)
            group_type = player_config.get_value(CONF_GROUP_TYPE)
            with suppress(PlayerUnavailableError):
                self._register_group_player(
                    player_config.player_id,
                    group_type,
                    player_config.name or player_config.default_name,
                    members,
                )

    def _register_group_player(
        self, group_player_id: str, group_type: str, name: str, members: Iterable[str]
    ) -> Player:
        """Register a syncgroup player."""
        player_features = {PlayerFeature.POWER, PlayerFeature.VOLUME_SET}

        if not (self.mass.players.get(x) for x in members):
            raise PlayerUnavailableError("One or more members are not available!")

        if group_type == GROUP_TYPE_UNIVERSAL:
            model_name = "Universal Group"
            manufacturer = self.name
            # register dynamic route for the ugp stream
            route_path = f"/ugp/{group_player_id}.aac"
            self._on_unload.append(
                self.mass.streams.register_dynamic_route(route_path, self._serve_ugp_stream)
            )
        elif player_provider := self.mass.get_provider(group_type):
            # grab additional details from one of the provider's players
            if TYPE_CHECKING:
                player_provider = cast(PlayerProvider, player_provider)
            model_name = "Sync Group"
            manufacturer = self.mass.get_provider(group_type).name
            for feature in (
                PlayerFeature.PAUSE,
                PlayerFeature.VOLUME_MUTE,
            ):
                if all(x for x in player_provider.players if feature in x.supported_features):
                    player_features.add(feature)
        else:
            raise PlayerUnavailableError(f"Provider for syncgroup {group_type} is not available!")

        player = Player(
            player_id=group_player_id,
            provider=self.instance_id,
            type=PlayerType.GROUP,
            name=name,
            available=True,
            powered=False,
            device_info=DeviceInfo(model=model_name, manufacturer=manufacturer),
            supported_features=tuple(player_features),
            group_childs=set(members),
            active_source=group_player_id,
        )

        self.mass.players.register_or_update(player)
        self._update_attributes(player)
        return player

    def _get_sync_leader(self, group_player: Player) -> Player | None:
        """Get the active sync leader player for the syncgroup."""
        if group_player.synced_to:
            # should not happen but just in case...
            return self.mass.players.get(group_player.synced_to)
        # Return the (first/only) player that has group childs
        for child_player in self.mass.players.iter_group_members(
            group_player, only_powered=False, only_playing=False, active_only=False
        ):
            if child_player.group_childs:
                return child_player
        return None

    def _select_sync_leader(self, group_player: Player) -> Player | None:
        """Select the active sync leader player for a syncgroup."""
        if sync_leader := self._get_sync_leader(group_player):
            return sync_leader
        # select new sync leader: return the first active player
        for child_player in self.mass.players.iter_group_members(group_player, active_only=True):
            if child_player.active_group not in (None, group_player.player_id):
                continue
            if (
                child_player.active_source
                and child_player.active_source != group_player.active_source
            ):
                continue
            return child_player
        # fallback select new sync leader: simply return the first (available) player
        for child_player in self.mass.players.iter_group_members(
            group_player, only_powered=False, only_playing=False, active_only=False
        ):
            return child_player
        # this really should not be possible
        raise RuntimeError("Impossible to select sync leader for syncgroup")

    async def _sync_syncgroup(self, group_player: Player) -> None:
        """Sync all (possible) players of a syncgroup."""
        sync_leader = self._select_sync_leader(group_player)
        members_to_sync: list[str] = []
        for member in self.mass.players.iter_group_members(group_player, active_only=True):
            if sync_leader.player_id == member.player_id:
                # skip sync leader
                continue
            if member.synced_to == sync_leader.player_id:
                # already synced
                continue
            if member.synced_to and member.synced_to != sync_leader.player_id:
                # unsync first
                await self.mass.players.cmd_unsync(member.player_id)
            members_to_sync.append(member.player_id)
        if members_to_sync:
            await self.mass.players.cmd_sync_many(sync_leader.player_id, members_to_sync)

    async def _on_mass_player_added_event(self, event: MassEvent) -> None:
        """Handle player added event from player controller."""
        await self._register_all_players()

    def _update_attributes(self, player: Player) -> None:
        """Update attributes of a player."""
        for child_player in self.mass.players.iter_group_members(player, active_only=True):
            # just grab the first active player
            player.state = child_player.state
            if player.current_media:
                player.current_media = child_player.current_media
            player.elapsed_time = child_player.elapsed_time
            player.elapsed_time_last_updated = child_player.elapsed_time_last_updated
            break
        else:
            player.state = PlayerState.IDLE
            player.active_source = player.player_id
        self.mass.players.update(player.player_id)

    async def _serve_ugp_stream(self, request: web.Request) -> web.Response:
        """Serve the UGP (multi-client) flow stream audio to a player."""
        ugp_player_id = request.path.rsplit(".")[0].rsplit("/")[-1]
        child_player_id = request.query.get("player_id")  # optional!

        if not (ugp_player := self.mass.players.get(ugp_player_id)):
            raise web.HTTPNotFound(reason=f"Unknown UGP player: {ugp_player_id}")

        if not (stream := self.ugp_streams.get(ugp_player_id, None)) or stream.done:
            raise web.HTTPNotFound(body=f"There is no active UGP stream for {ugp_player_id}!")

        http_profile: str = await self.mass.config.get_player_config_value(
            child_player_id, CONF_HTTP_PROFILE
        )
        headers = {
            **DEFAULT_STREAM_HEADERS,
            "Content-Type": "audio/aac",
            "Accept-Ranges": "none",
            "Cache-Control": "no-cache",
            "Connection": "close",
        }

        resp = web.StreamResponse(status=200, reason="OK", headers=headers)
        if http_profile == "forced_content_length":
            resp.content_length = 4294967296
        elif http_profile == "chunked":
            resp.enable_chunked_encoding()

        await resp.prepare(request)

        # return early if this is not a GET request
        if request.method != "GET":
            return resp

        # all checks passed, start streaming!
        self.logger.debug(
            "Start serving UGP flow audio stream for UGP-player %s to %s",
            ugp_player.display_name,
            child_player_id or request.remote,
        )
        async for chunk in stream.subscribe():
            try:
                await resp.write(chunk)
            except (ConnectionError, ConnectionResetError):
                break

        return resp

    def _filter_members(self, provider: str, members: list[str]) -> list[str]:
        """Filter out members that are not valid players."""
        if provider != GROUP_TYPE_UNIVERSAL:
            return [
                x
                for x in members
                if (player := self.mass.players.get(x)) and player.provider == provider
            ]
        # cleanup members - filter out impossible choices
        syncgroup_childs: list[str] = []
        for member in members:
            if not member.startswith(SYNCGROUP_PREFIX):
                continue
            if syncgroup := self.mass.players.get(member):
                syncgroup_childs.extend(syncgroup.group_childs)
        # we filter out other UGP players and syncgroup childs
        # if their parent is already in the list
        return [
            x
            for x in members
            if self.mass.players.get(x)
            and x not in syncgroup_childs
            and not x.startswith(UNIVERSAL_PREFIX)
        ]
