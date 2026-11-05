"""Client and parsing for the community Deadlock API (https://api.deadlock-api.com).

No key is needed. Docs: https://api.deadlock-api.com/docs (OpenAPI spec at
https://api.deadlock-api.com/openapi.json), operation ``match_history``.

GET /v1/players/{account_id}/match-history returns the stored history (ranked and
normal matches together, newest first). Stored history is limited to 100 req/s per
IP. ``force_refetch=true`` is limited to 1 req/h per IP (10 req/h globally), so this
module never sends it. A 429 still carries the stored history as a fallback body.

"As it ends" means as this API ingests the match, which can lag the real end.
"""

import aiohttp

from utils.exceptions import LiveLOLError
from utils.logger_config import logger

BASE_URL = "https://api.deadlock-api.com"
HEADERS = {"Accept": "application/json", "User-Agent": "LiveLOL/1.0"}

# Numeric match_mode values, in the order the API's docs list the modes
# (unranked, private_lobby, coop_bot, ranked, ...). Checked against live history:
# ranked entries carry 4 and the ranked_* fields, normal ones carry 1.
MATCH_MODE_UNRANKED = 1
MATCH_MODE_RANKED = 4

# ranked_display_badge: tier = leading digits, subtier = last digit.
RANK_TIER_NAMES = {
    0: "Obscurus",
    1: "Initiate",
    2: "Seeker",
    3: "Acolyte",
    4: "Sentinel",
    5: "Mystic",
    6: "Ritualist",
    7: "Emissary",
    8: "Oracle",
    9: "Phantom",
    10: "Ascendant",
    11: "Eternus",
}

# Newest matches announced per player per cycle, so a long outage cannot flood a
# channel. The pointer still jumps to the newest match.
MAX_ANNOUNCE_PER_CYCLE = 5


class DeadlockAPIError(LiveLOLError):
    """Raised when the Deadlock API is unreachable or answers unexpectedly."""

    def __init__(self, detail: str = "The Deadlock API was unresponsive."):
        self.message = f"📡 **Deadlock API Issue:** {detail}"
        super().__init__(self.message)


class DeadlockPlayerNotFoundError(DeadlockAPIError):
    """Raised when an account id has no match history on the API."""

    def __init__(self, detail: str = "Player not found."):
        super().__init__(detail)
        self.message = f"🔍 **Search Error:** {detail}"
        self.args = (self.message,)


async def get_match_history(session, account_id):
    """Return the stored match history list for a Steam account id (SteamID3)."""
    url = f"{BASE_URL}/v1/players/{account_id}/match-history"
    try:
        async with session.get(url, headers=HEADERS) as response:
            # 429 returns the stored history as a fallback body, so it is usable.
            if response.status in (200, 429):
                data = await response.json()
                if isinstance(data, list):
                    return data
                raise DeadlockAPIError(f"Unexpected response ({response.status}).")
            raise DeadlockAPIError(f"Error {response.status} from the API.")
    except aiohttp.ClientError as e:
        raise DeadlockAPIError("Network connection failed.") from e


_hero_names = {}


async def get_hero_name(session, hero_id):
    """Hero name for an id, cached after the first successful fetch."""
    if not _hero_names:
        try:
            async with session.get(
                f"{BASE_URL}/v1/assets/heroes", headers=HEADERS
            ) as response:
                if response.status == 200:
                    for hero in await response.json():
                        _hero_names[hero["id"]] = hero["name"]
        except (aiohttp.ClientError, KeyError, TypeError, ValueError) as e:
            logger.warning(f"⚠️ Could not load Deadlock hero names: {e}")
    return _hero_names.get(hero_id, f"Hero #{hero_id}")


def newest_match_id(history):
    ids = [e.get("match_id") for e in history if e.get("match_id")]
    return max(ids) if ids else None


def new_matches(history, last_match_id):
    """Entries newer than ``last_match_id``, oldest first, capped to the newest few.

    With no stored pointer nothing is new: a first sight only records the pointer.
    """
    if last_match_id is None:
        return []
    fresh = [e for e in history if e.get("match_id") and e["match_id"] > last_match_id]
    fresh.sort(key=lambda e: e["match_id"])
    return fresh[-MAX_ANNOUNCE_PER_CYCLE:]


def entry_won(entry):
    """True if the player's team won (match_result is the winning team)."""
    return entry.get("match_result") == entry.get("player_team")


def is_ranked(entry):
    return entry.get("match_mode") == MATCH_MODE_RANKED


def badge_name(badge):
    """'Eternus 6' style label for a ranked_display_badge, or None."""
    if badge is None:
        return None
    tier, subtier = divmod(badge, 10)
    name = RANK_TIER_NAMES.get(tier)
    if name is None:
        return None
    return f"{name} {subtier}" if subtier else name
