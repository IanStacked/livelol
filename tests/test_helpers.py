from utils.helpers import (
    extract_match_info,
    next_streak,
    parse_region,
    parse_riot_id,
    streak_label,
)


def test_parse_riot_id_valid():
    assert parse_riot_id("Ninja#TAG") == ("Ninja", "tag")  # capitalized tag
    assert parse_riot_id("Ninja#tag") == ("Ninja", "tag")  # lowercase tag
    assert parse_riot_id("NiNJa#TaG") == ("NiNJa", "tag")  # random caps


def test_parse_riot_id_invalid():
    assert parse_riot_id("NinjaTag") is None  # no hashtag
    assert parse_riot_id("Ninja#") is None  # no tag
    assert parse_riot_id("#tag") is None  # no username
    assert parse_riot_id("Rob\nert\n#\nFu\nn") is None  # newline character everywhere
    assert parse_riot_id("Robert\n#Fun") is None  # newline character before hashtag
    assert parse_riot_id("Robert#\nFun") is None  # newline character after hashtag


def test_parse_region_valid():
    assert parse_region("na1") == "na1"  # normal case
    assert parse_region("NA1") == "na1"  # region capitalized
    assert parse_region("   na1   ") == "na1"  # whitespace around region


def test_parse_region_invalid():
    assert parse_region("") is None  # empty region
    assert parse_region("\nna1") is None  # newline character in region


def test_next_streak_from_zero():
    assert next_streak(0, True) == 1  # first win
    assert next_streak(0, False) == -1  # first loss
    assert next_streak(None, True) == 1  # missing streak treated as 0
    assert next_streak(None, False) == -1


def test_next_streak_extends():
    assert next_streak(3, True) == 4  # win extends a win streak
    assert next_streak(-3, False) == -4  # loss extends a loss streak


def test_next_streak_resets_on_flip():
    assert next_streak(-4, True) == 1  # a win ends a loss streak
    assert next_streak(4, False) == -1  # a loss ends a win streak


def test_streak_label_below_threshold():
    assert streak_label(0) is None
    assert streak_label(2) is None  # under the 3-game threshold
    assert streak_label(-2) is None
    assert streak_label(None) is None


def test_streak_label_at_threshold():
    assert streak_label(3) == "🔥 3-game win streak"
    assert streak_label(5) == "🔥 5-game win streak"
    assert streak_label(-3) == "❄️ 3-game loss streak"
    assert streak_label(-5) == "❄️ 5-game loss streak"


def test_extract_match_info_includes_match_id():
    match_dto = {
        "metadata": {"matchId": "NA1_123"},
        "info": {
            "participants": [
                {
                    "puuid": "abc",
                    "championName": "Ahri",
                    "kills": 5,
                    "deaths": 2,
                    "assists": 7,
                    "win": True,
                },
            ],
        },
    }
    info = extract_match_info(match_dto, "abc")
    assert info["match_id"] == "NA1_123"
    assert info["win"] is True
    assert info["target_champion"] == "Ahri"


def test_extract_match_info_target_absent():
    match_dto = {
        "metadata": {"matchId": "NA1_123"},
        "info": {
            "participants": [
                {
                    "puuid": "someone-else",
                    "championName": "Ahri",
                    "kills": 5,
                    "deaths": 2,
                    "assists": 7,
                    "win": True,
                },
            ],
        },
    }
    # The tracked puuid is not in the match: None, not an UnboundLocalError.
    assert extract_match_info(match_dto, "abc") is None


def test_extract_match_info_no_participants():
    assert extract_match_info({"metadata": {}, "info": {}}, "abc") is None
