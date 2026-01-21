# This file is for miscellaneous logic
# If you notice a group of these functions having similar functionality,
# make a separate file for them.

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
    clean_riot_id = unclean_riot_id.strip()
    if "#" not in clean_riot_id:
        return None
    parts = clean_riot_id.split("#", 1)
    username = parts[0]
    tagline = parts[1]
    if not username or not tagline:
        return None
    # Taglines are case-insensitive. Lowercasing ensures that
    # identical RiotIDs are handled consistently
    return (username, tagline.lower())
