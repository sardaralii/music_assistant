"""Helper and utility functions."""

from __future__ import annotations

import asyncio
import os
import re
import socket
from collections.abc import Callable
from collections.abc import Set as AbstractSet
from typing import Any, TypeVar
from urllib.parse import urlparse
from uuid import UUID

T = TypeVar("T")
CALLBACK_TYPE = Callable[[], None]

keyword_pattern = re.compile("title=|artist=")
title_pattern = re.compile(r"title=\"(?P<title>.*?)\"")
artist_pattern = re.compile(r"artist=\"(?P<artist>.*?)\"")
dot_com_pattern = re.compile(r"(?P<netloc>\(?\w+\.(?:\w+\.)?(\w{2,3})\)?)")
ad_pattern = re.compile(r"((ad|advertisement)_)|^AD\s\d+$|ADBREAK", flags=re.IGNORECASE)
title_artist_order_pattern = re.compile(r"(?P<title>.+)\sBy:\s(?P<artist>.+)", flags=re.IGNORECASE)
multi_space_pattern = re.compile(r"\s{2,}")
end_junk_pattern = re.compile(r"(.+?)(\s\W+)$")

VERSION_PARTS = (
    # list of common version strings
    "version",
    "live",
    "edit",
    "remix",
    "mix",
    "acoustic",
    "instrumental",
    "karaoke",
    "remaster",
    "versie",
    "unplugged",
    "disco",
    "akoestisch",
    "deluxe",
)
IGNORE_TITLE_PARTS = (
    # strings that may be stripped off a title part
    # (most important the featuring parts)
    "feat.",
    "featuring",
    "ft.",
    "with ",
    "explicit",
)


def filename_from_string(string: str) -> str:
    """Create filename from unsafe string."""
    keepcharacters = (" ", ".", "_")
    return "".join(c for c in string if c.isalnum() or c in keepcharacters).rstrip()


def try_parse_int(possible_int: Any, default: int | None = 0) -> int | None:
    """Try to parse an int."""
    try:
        return int(possible_int)
    except (TypeError, ValueError):
        return default


def try_parse_float(possible_float: Any, default: float | None = 0.0) -> float | None:
    """Try to parse a float."""
    try:
        return float(possible_float)
    except (TypeError, ValueError):
        return default


def try_parse_bool(possible_bool: Any) -> bool:
    """Try to parse a bool."""
    if isinstance(possible_bool, bool):
        return possible_bool
    return possible_bool in ["true", "True", "1", "on", "ON", 1]


def try_parse_duration(duration_str: str) -> float:
    """Try to parse a duration in seconds from a duration (HH:MM:SS) string."""
    milliseconds = float("0." + duration_str.split(".")[-1]) if "." in duration_str else 0.0
    duration_parts = duration_str.split(".")[0].split(",")[0].split(":")
    if len(duration_parts) == 3:
        seconds = sum(x * int(t) for x, t in zip([3600, 60, 1], duration_parts, strict=False))
    elif len(duration_parts) == 2:
        seconds = sum(x * int(t) for x, t in zip([60, 1], duration_parts, strict=False))
    else:
        seconds = int(duration_parts[0])
    return seconds + milliseconds


def create_sort_name(input_str: str) -> str:
    """Create (basic/simple) sort name/title from string."""
    input_str = input_str.lower().strip()
    for item in ["the ", "de ", "les ", "dj ", "las ", "los ", "le ", "la ", "el ", "a ", "an "]:
        if input_str.startswith(item):
            input_str = input_str.replace(item, "") + f", {item}"
    return input_str.strip()


def parse_title_and_version(title: str, track_version: str | None = None) -> tuple[str, str]:
    """Try to parse version from the title."""
    version = track_version or ""
    for regex in (r"\(.*?\)", r"\[.*?\]", r" - .*"):
        for title_part in re.findall(regex, title):
            for ignore_str in IGNORE_TITLE_PARTS:
                if ignore_str in title_part.lower():
                    title = title.replace(title_part, "").strip()
                    continue
            for version_str in VERSION_PARTS:
                if version_str not in title_part.lower():
                    continue
                version = (
                    title_part.replace("(", "")
                    .replace(")", "")
                    .replace("[", "")
                    .replace("]", "")
                    .replace("-", "")
                    .strip()
                )
                title = title.replace(title_part, "").strip()
                return (title, version)
    return title, version


def strip_ads(line: str) -> str:
    """Strip Ads from line."""
    if ad_pattern.search(line):
        return "Advert"
    return line


def strip_url(line: str) -> str:
    """Strip URL from line."""
    return (
        " ".join([p for p in line.split() if (not urlparse(p).scheme or not urlparse(p).netloc)])
    ).rstrip()


def strip_dotcom(line: str) -> str:
    """Strip scheme-less netloc from line."""
    return dot_com_pattern.sub("", line)


def strip_end_junk(line: str) -> str:
    """Strip non-word info from end of line."""
    return end_junk_pattern.sub(r"\1", line)


def swap_title_artist_order(line: str) -> str:
    """Swap title/artist order in line."""
    return title_artist_order_pattern.sub(r"\g<artist> - \g<title>", line)


def strip_multi_space(line: str) -> str:
    """Strip multi-whitespace from line."""
    return multi_space_pattern.sub(" ", line)


def multi_strip(line: str) -> str:
    """Strip assorted junk from line."""
    return strip_multi_space(
        swap_title_artist_order(strip_end_junk(strip_dotcom(strip_url(strip_ads(line)))))
    ).rstrip()


def clean_stream_title(line: str) -> str:
    """Strip junk text from radio streamtitle."""
    title: str = ""
    artist: str = ""

    if not keyword_pattern.search(line):
        return multi_strip(line)

    if match := title_pattern.search(line):
        title = multi_strip(match.group("title"))

    if match := artist_pattern.search(line):
        possible_artist = multi_strip(match.group("artist"))
        if possible_artist and possible_artist != title:
            artist = possible_artist

    if not title and not artist:
        return ""

    if title:
        if re.search(" - ", title) or not artist:
            return title
        if artist:
            return f"{artist} - {title}"

    if artist:
        return artist

    return line


async def get_ip() -> str:
    """Get primary IP-address for this host."""

    def _get_ip() -> str:
        """Get primary IP-address for this host."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            sock.connect(("10.255.255.255", 1))
            _ip = str(sock.getsockname()[0])
        except Exception:
            _ip = "127.0.0.1"
        finally:
            sock.close()
        return _ip

    return await asyncio.to_thread(_get_ip)


async def is_port_in_use(port: int) -> bool:
    """Check if port is in use."""

    def _is_port_in_use() -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _sock:
            try:
                _sock.bind(("0.0.0.0", port))
            except OSError:
                return True
        return False

    return await asyncio.to_thread(_is_port_in_use)


async def select_free_port(range_start: int, range_end: int) -> int:
    """Automatically find available port within range."""
    for port in range(range_start, range_end):
        if not await is_port_in_use(port):
            return port
    msg = "No free port available"
    raise OSError(msg)


async def get_ip_from_host(dns_name: str) -> str | None:
    """Resolve (first) IP-address for given dns name."""

    def _resolve() -> str | None:
        try:
            return socket.gethostbyname(dns_name)
        except Exception:
            # fail gracefully!
            return None

    return await asyncio.to_thread(_resolve)


async def get_ip_pton(ip_string: str | None = None) -> bytes:
    """Return socket pton for local ip."""
    if ip_string is None:
        ip_string = await get_ip()
    try:
        return await asyncio.to_thread(socket.inet_pton, socket.AF_INET, ip_string)
    except OSError:
        return await asyncio.to_thread(socket.inet_pton, socket.AF_INET6, ip_string)


def get_folder_size(folderpath: str) -> float:
    """Return folder size in gb."""
    total_size = 0
    for dirpath, _dirnames, filenames in os.walk(folderpath):
        for _file in filenames:
            _fp = os.path.join(dirpath, _file)
            total_size += os.path.getsize(_fp)
    return total_size / float(1 << 30)


def merge_dict(
    base_dict: dict[Any, Any], new_dict: dict[Any, Any], allow_overwite: bool = False
) -> dict[Any, Any]:
    """Merge dict without overwriting existing values."""
    final_dict = base_dict.copy()
    for key, value in new_dict.items():
        if final_dict.get(key) and isinstance(value, dict):
            final_dict[key] = merge_dict(final_dict[key], value)
        if final_dict.get(key) and isinstance(value, tuple):
            final_dict[key] = merge_tuples(final_dict[key], value)
        if final_dict.get(key) and isinstance(value, list):
            final_dict[key] = merge_lists(final_dict[key], value)
        elif not final_dict.get(key) or allow_overwite:
            final_dict[key] = value
    return final_dict


def merge_tuples(base: tuple[Any, ...], new: tuple[Any, ...]) -> tuple[Any, ...]:
    """Merge 2 tuples."""
    return tuple(x for x in base if x not in new) + tuple(new)


def merge_lists(base: list[Any], new: list[Any]) -> list[Any]:
    """Merge 2 lists."""
    return [x for x in base if x not in new] + list(new)


def get_changed_keys(
    dict1: dict[str, Any],
    dict2: dict[str, Any],
    ignore_keys: list[str] | None = None,
) -> AbstractSet[str]:
    """Compare 2 dicts and return set of changed keys."""
    return get_changed_values(dict1, dict2, ignore_keys).keys()


def get_changed_values(
    dict1: dict[str, Any],
    dict2: dict[str, Any],
    ignore_keys: list[str] | None = None,
) -> dict[str, tuple[Any, Any]]:
    """
    Compare 2 dicts and return dict of changed values.

    dict key is the changed key, value is tuple of old and new values.
    """
    if not dict1 and not dict2:
        return {}
    if not dict1:
        return {key: (None, value) for key, value in dict2.items()}
    if not dict2:
        return {key: (None, value) for key, value in dict1.items()}
    changed_values = {}
    for key, value in dict2.items():
        if ignore_keys and key in ignore_keys:
            continue
        if key not in dict1:
            changed_values[key] = (None, value)
        elif isinstance(value, dict):
            changed_values.update(get_changed_values(dict1[key], value, ignore_keys))
        elif dict1[key] != value:
            changed_values[key] = (dict1[key], value)
    return changed_values


def empty_queue(q: asyncio.Queue[T]) -> None:
    """Empty an asyncio Queue."""
    for _ in range(q.qsize()):
        try:
            q.get_nowait()
            q.task_done()
        except (asyncio.QueueEmpty, ValueError):
            pass


def is_valid_uuid(uuid_to_test: str) -> bool:
    """Check if uuid string is a valid UUID."""
    try:
        uuid_obj = UUID(uuid_to_test)
    except (ValueError, TypeError):
        return False
    return str(uuid_obj) == uuid_to_test
