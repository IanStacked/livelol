# This file is for miscellaneous logic
# If you notice a group of these functions having similar functionality,
# make a separate file for them.

def parse_rank_info(old_data, new_data):
    return {
        "old_tier": old_data.get("tier"),
        "old_rank": old_data.get("rank"),
        "old_lp": old_data.get("LP"),
        "new_tier": new_data.get("tier"),
        "new_rank": new_data.get("rank"),
        "new_lp": new_data.get("LP"),
    }

def rank_difference(ranked_info) -> bool:
    old_tier = ranked_info.get("old_tier")
    old_rank = ranked_info.get("old_rank")
    old_lp = ranked_info.get("old_lp")
    new_tier = ranked_info.get("new_tier")
    new_rank = ranked_info.get("new_rank")
    new_lp = ranked_info.get("new_lp")
    return not (old_tier == new_tier and old_rank == new_rank and old_lp == new_lp)

def parse_region(unclean_region):
    """Parses an unclean_region string.

    Returns clean_region.lower() since lowercase is enforced for regions.
    """
    if not unclean_region:
        return None
    if "\n" in unclean_region:
        return None
    clean_region = unclean_region.strip()
    return clean_region.lower()

def check_new_riot_id(match_info, puuid, riot_id) -> str:
    """Checks if a user has changed their riotid and returns new riotid if new."""
    for p in match_info.get("participants"):
        if(p.get("puuid") == puuid):
            match_riot_id = p.get('riotIdGameName') + "#" + p.get('riotIdTagline')
            if(match_riot_id != riot_id):
                return match_riot_id
            else:
                return ""

def extract_match_info(match_dto, puuid):
    if not match_dto or "info" not in match_dto:
        return None
    participants = match_dto["info"].get("participants", [])
    for p in participants:
        if p.get("puuid") == puuid:
            target_champion = p.get("championName")
            target_kda = f"{p.get('kills')}/{p.get('deaths')}/{p.get('assists')}"
            win = p.get("win")
    info = {
        "target_champion": target_champion,
        "target_kda": target_kda,
        "participants": participants,
        "win": win,
    }
    return info

def parse_riot_id(unclean_riot_id):
    """Parses a Riot ID string and returns (username, tagline)."""
    if not unclean_riot_id or "#" not in unclean_riot_id:
        return None
    if "\n" in unclean_riot_id:
        return None
    clean_riot_id = " ".join(unclean_riot_id.split())
    parts = clean_riot_id.split("#")
    if len(parts) != 2:
        return None
    username = parts[0].strip()
    tagline = parts[1].strip()
    if not username or not tagline:
        return None
    # Taglines are case-insensitive. Lowercasing ensures that
    # identical RiotIDs are handled consistently
    return (username, tagline.lower())
