from utils.helpers import parse_region, parse_riot_id, valid_region


def test_parse_riot_id_valid():
    assert parse_riot_id("Ninja#TAG") == ("Ninja", "tag")  # capitalized tag
    assert parse_riot_id("Ninja#tag") == ("Ninja", "tag")  # lowercase tag
    assert parse_riot_id("NiNJa#TaG") == ("NiNJa", "tag")  # random caps

def test_parse_riot_id_invalid():
    assert parse_riot_id("NinjaTag") is None  # no hashtag
    assert parse_riot_id("Ninja#") is None  # no tag
    assert parse_riot_id("#tag") is None  # no username
    assert parse_riot_id("Rob\nert\n#\nFu\nn") is None # newline character everywhere
    assert parse_riot_id("Robert\n#Fun") is None # newline character before hashtag
    assert parse_riot_id("Robert#\nFun") is None # newline character after hashtag

def test_parse_region_valid():
    assert parse_region("na1") == "na1" # normal case
    assert parse_region("NA1") == "na1" # region capitalized
    assert parse_region("   na1   ") == "na1" # whitespace around region

def test_parse_region_invalid():
    assert parse_region("") is None # empty region
    assert parse_region("\nna1") is None # newline character in region

def test_valid_region_valid():
    assert valid_region("na1") is True # normal case

def test_valid_region_invalid():
    assert valid_region("na") is False # incorrect region
