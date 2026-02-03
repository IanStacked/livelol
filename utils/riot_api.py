import asyncio

import aiohttp

from utils.exceptions import (
    MatchNotFoundError,
    RateLimitError,
    RiotAPIError,
    UserNotFoundError,
)
from utils.logger_config import logger

# Core API Function


async def call_riot_api(session, url, headers, retries=3):
    for _attempt in range(retries):
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 1))
                    logger.warning(
                        f"⚠️ Rate Limit Hit! Sleeping for {retry_after} seconds...",
                    )
                    await asyncio.sleep(retry_after)
                    continue
                # other errors - dont retry
                elif response.status == 404:
                    return None
                elif response.status == 403:
                    raise RiotAPIError("Riot API Key is invalid or expired.")
                else:
                    raise RiotAPIError(f"Riot API Error {response.status}: {url}")
        except aiohttp.ClientError as e:
            raise RiotAPIError("Network Connection Failed") from e
    raise RateLimitError("Max retries exceeded for Riot API.")


# Specific Data Fetchers

async def get_summoner_info(session, puuid, region, riot_api_key):
    """Checks if a user has the correct region.

    This API call is unique in that it will only return a 200 status if the users
    region is correct.
    """
    api_url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    headers = {
        "X-Riot-Token": riot_api_key,
        "Accept": "application/json",
        "User-Agent": "LeagueHelperApp/1.0",
    }
    summoner_info = await call_riot_api(session, api_url, headers)
    return summoner_info

async def get_recent_match_info(session, puuid, cluster, riot_api_key):
    api_url = f"https://{cluster}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&count=1"
    headers = {
        "X-Riot-Token": riot_api_key,
        "Accept": "application/json",
        "User-Agent": "LeagueHelperApp/1.0",
    }
    match_id = await call_riot_api(session, api_url, headers)
    if match_id is None:
        raise MatchNotFoundError()
    api_url = f"https://{cluster}.api.riotgames.com/lol/match/v5/matches/{match_id[0]}"
    match_info = await call_riot_api(session, api_url, headers)
    if match_info is None:
        raise MatchNotFoundError()
    return match_info


async def get_puuid(session, game_name, tag_line, riot_api_key):
    api_url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    headers = {
        "X-Riot-Token": riot_api_key,
        "Accept": "application/json",
        "User-Agent": "LeagueHelperApp/1.0",
    }
    data = await call_riot_api(session, api_url, headers)
    if data is None:
        raise UserNotFoundError(f"User {game_name}#{tag_line} not found.")
    return data.get("puuid")


async def get_ranked_info(session, puuid, region, riot_api_key):
    api_url = f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    headers = {
        "X-Riot-Token": riot_api_key,
        "Accept": "application/json",
        "User-Agent": "LeagueHelperApp/1.0",
    }
    data = await call_riot_api(session, api_url, headers)
    if data is None:
        raise UserNotFoundError(f"User with puuid: {puuid} not found.")
    soloq = None
    for entry in data:
        if entry.get("queueType") == "RANKED_SOLO_5x5":
            soloq = entry
            break
    if soloq:
        return {
            "tier": soloq.get("tier"),
            "rank": soloq.get("rank"),
            "LP": soloq.get("leaguePoints"),
        }
    else:
        return {"tier": "UNRANKED", "rank": "", "LP": 0}
