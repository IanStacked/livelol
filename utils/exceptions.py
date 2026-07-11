class LiveLOLError(Exception):
    """Base exception for all bot errors."""

    def __init__(self, message: str = "An unexpected error occurred."):
        # We do not provide a "detail" variable, but rather go straight to message.
        # This is because this is the ultimate base exception,
        # there is no prefix information to add.
        self.message = message
        super().__init__(self.message)


class RiotAPIError(LiveLOLError):
    """Base exception for all Riot API related errors."""

    def __init__(self, detail: str = "The Riot API was unresponsive."):
        prefix = "📡 **Riot API Issue:**"
        self.message = f"{prefix} {detail}"
        super().__init__(self.message)


class UserNotFoundError(RiotAPIError):
    """Raised when a users Riot ID is not recognized by Riot."""

    def __init__(self, detail: str = "Player not found."):
        prefix = "🔍 **Search Error:**"
        self.message = f"{prefix} {detail}"
        super().__init__(self.message)


class RateLimitError(RiotAPIError):
    """Raised when a rate limit was hit by an API call."""

    def __init__(self, detail: str = "API rate limit hit."):
        prefix = ""
        self.message = f"{prefix} {detail}"
        super().__init__(self.message)


class ServiceUnavailableError(RiotAPIError):
    """Raised when Cloudflare or a specific Shard is rejecting us."""

    def __init__(self, detail: str = "Shard is unresponsive."):
        prefix = "☁️ **Service Issue:**"
        self.message = f"{prefix} {detail}"
        super().__init__(self.message)


class MatchNotFoundError(RiotAPIError):
    """Raised when a player has no recent match history for the specified queue."""

    def __init__(self, detail: str = "No recent matches found."):
        prefix = "🎮 **Match Error:**"
        self.message = f"{prefix} {detail}"
        super().__init__(self.message)


class DatabaseError(LiveLOLError):
    """Base exception for all database related errors."""

    def __init__(self, detail: str = "Failed to update database records."):
        prefix = "💾 **Database Error:**"
        self.message = f"{prefix} {detail}"
        super().__init__(self.message)
