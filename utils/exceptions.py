class RiotAPIError(Exception):
    """Base exceptions for all Riot API related errors."""
    pass


class UserNotFoundError(RiotAPIError):
    """Raised when a users Riot ID is not recognized by Riot."""
    pass


class RateLimitError(RiotAPIError):
    """Raised when a rate limit was hit by an API call."""
    pass
