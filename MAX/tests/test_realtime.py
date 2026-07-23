import asyncio
from uuid import UUID

from app.api.realtime_routes import event_message, list_event_stream


class DisconnectedRequest:
    async def is_disconnected(self) -> bool:
        return True


def test_event_message_is_valid_sse() -> None:
    assert event_message("list_changed", {"version": 7}) == (
        'event: list_changed\ndata: {"version":7}\n\n'
    )


def test_stream_starts_with_current_version() -> None:
    async def first_event() -> str:
        stream = list_event_stream(
            DisconnectedRequest(),  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
            UUID("00000000-0000-0000-0000-000000000001"),
            UUID("00000000-0000-0000-0000-000000000002"),
            4,
        )
        event = await anext(stream)
        await stream.aclose()
        return event

    assert asyncio.run(first_event()) == 'event: ready\ndata: {"version":4}\n\n'
