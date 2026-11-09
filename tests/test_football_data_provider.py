from tools.football_data_provider import parse_football_data_csv


SAMPLE = """Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,BbAvH,BbAvD,BbAvA
SP1,01/07/26,Ath Madrid,Barcelona,1,2,A,2.10,3.40,3.20
SP1,08/07/26,Barcelona,Ath Madrid,2,0,H,1.70,3.80,4.60
SP1,15/07/26,Real Madrid,Sevilla,,,,1.40,4.50,7.00
"""


def test_parse_football_data_csv_normalizes_finished_fixtures_and_odds():
    fixtures = parse_football_data_csv(
        SAMPLE, league_id=140, from_date="2026-07-01", to_date="2026-07-31"
    )
    assert len(fixtures) == 2
    first = fixtures[0]
    assert first["fixture"]["status"]["short"] == "FT"
    assert first["teams"]["home"]["name"] == "Ath Madrid"
    assert first["teams"]["away"]["name"] == "Barcelona"
    assert first["goals"] == {"home": 1, "away": 2}
    assert first["historical_odds"]["home"] == 2.10
    assert first["historical_odds"]["draw"] == 3.40
    assert first["historical_odds"]["away"] == 3.20
    assert fixtures[0]["teams"]["home"]["id"] == fixtures[1]["teams"]["away"]["id"]


def test_parse_football_data_csv_filters_dates_and_unfinished_rows():
    fixtures = parse_football_data_csv(
        SAMPLE, league_id=140, from_date="2026-07-01", to_date="2026-07-10"
    )
    assert len(fixtures) == 2
    assert all(item["goals"]["home"] is not None for item in fixtures)


def test_parse_football_data_csv_rejects_wrong_schema():
    import pytest
    with pytest.raises(ValueError, match="schema mismatch"):
        parse_football_data_csv(
            "Date,HomeTeam\n01/07/26,Ath Madrid\n",
            league_id=140, from_date="2026-07-01", to_date="2026-07-31"
        )
