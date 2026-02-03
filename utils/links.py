from utils.constants import DEEPLOL_REGIONS, OPGG_REGIONS


def deeplol_link(encoded_riot_id, region):
    """Attempts to form a valid deeplol link."""
    if(region not in DEEPLOL_REGIONS):
        return None
    deeplol_region = DEEPLOL_REGIONS.get(region)
    return f"https://www.deeplol.gg/summoner/{deeplol_region}/{encoded_riot_id}"

def opgg_link(encoded_riot_id, region):
    """Attempts to form a valid op.gg link."""
    if(region not in OPGG_REGIONS):
        return None
    opgg_region = OPGG_REGIONS.get(region)
    return f"https://op.gg/lol/summoners/{opgg_region}/{encoded_riot_id}"
