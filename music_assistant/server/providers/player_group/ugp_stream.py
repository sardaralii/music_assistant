"""
Implementation of a Stream for the Universal Group Player.

Basically this is like a fake radio radio stream (AAC) format with multiple subscribers.
The AAC format is chosen because it is widely supported and has a good balance between
quality and bandwidth and also allows for mid-stream joining of (extra) players.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable

from music_assistant.common.models.enums import ContentType
from music_assistant.common.models.media_items import AudioFormat
from music_assistant.server.helpers.audio import get_ffmpeg_stream

# ruff: noqa: ARG002

UGP_FORMAT = AudioFormat(
    content_type=ContentType.PCM_F32LE,
    sample_rate=44100,
    bit_depth=32,
)


class UGPStream:
    """
    Implementation of a Stream for the Universal Group Player.

    Basically this is like a fake radio radio stream (AAC) format with multiple subscribers.
    The AAC format is chosen because it is widely supported and has a good balance between
    quality and bandwidth and also allows for mid-stream joining of (extra) players.
    """

    def __init__(
        self,
        audio_source: AsyncGenerator[bytes, None],
        audio_format: AudioFormat,
    ) -> None:
        """Initialize UGP Stream."""
        self.audio_source = audio_source
        self.input_format = audio_format
        self.output_format = AudioFormat(content_type=ContentType.AAC)
        self.subscribers: list[Callable[[bytes], Awaitable]] = []
        self._task: asyncio.Task | None = None
        self._done: asyncio.Event = asyncio.Event()

    @property
    def done(self) -> bool:
        """Return if this stream is already done."""
        return self._done.is_set() and self._task and self._task.done()

    async def stop(self) -> None:
        """Stop/cancel the stream."""
        if self._done.is_set():
            return
        if self._task and not self._task.done():
            self._task.cancel()
        self._done.set()

    async def subscribe(self) -> AsyncGenerator[bytes, None]:
        """Subscribe to the raw/unaltered audio stream."""
        # start the runner as soon as the (first) client connects
        if not self._task:
            self._task = asyncio.create_task(self._runner())
        queue = asyncio.Queue(1)
        try:
            self.subscribers.append(queue.put)
            while True:
                chunk = await queue.get()
                if not chunk:
                    break
                yield chunk
        finally:
            self.subscribers.remove(queue.put)

    async def _runner(self) -> None:
        """Run the stream for the given audio source."""
        await asyncio.sleep(0.25)  # small delay to allow subscribers to connect
        async for chunk in get_ffmpeg_stream(
            audio_input=self.audio_source,
            input_format=self.input_format,
            output_format=self.output_format,
            # TODO: enable readrate limiting + initial burst once we have a newer ffmpeg version
            # extra_input_args=["-readrate", "1.15"],
        ):
            await asyncio.gather(*[sub(chunk) for sub in self.subscribers], return_exceptions=True)
        # empty chunk when done
        await asyncio.gather(*[sub(b"") for sub in self.subscribers], return_exceptions=True)
        self._done.set()
