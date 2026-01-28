class RiotAPIError(Exception):
    """Base exception for all Riot API related errors."""
    pass


class UserNotFoundError(RiotAPIError):
    """Raised when a users Riot ID is not recognized by Riot."""
    pass


class RateLimitError(RiotAPIError):
    """Raised when a rate limit was hit by an API call."""
    pass

class DatabaseError(Exception):
    """Base exception for all database related errors."""
