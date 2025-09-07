"""Fallback roster manager to keep GUI stable when real roster unavailable."""


class _FallbackRosterManager:  # pragma: no cover - simple resilience shim
    def lookup_member(self, _call):  # noqa: D401
        return None

    def search_callsigns(self, _prefix, _limit=10):  # noqa: D401
        return []

    async def ensure_roster_updated(self, *_, **__):  # noqa: D401
        return False, "No roster manager available"

    def get_status(self):  # noqa: D401
        return {"member_count": 0, "last_update": None, "needs_update": False}


__all__ = ["_FallbackRosterManager"]
