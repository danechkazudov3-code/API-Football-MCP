from tools.open_matchday_provider import LEAGUES, _form


def test_open_matchday_maps_major_european_leagues():
    assert LEAGUES[140][0] == "ESP_1_la-liga"
    assert LEAGUES[39][0] == "ENG_1_premier-league"
    assert LEAGUES[135][0] == "ITA_1_serie-a"
    assert LEAGUES[78][0] == "GER_1_bundesliga"
    assert LEAGUES[61][0] == "FRA_1_ligue-1"


def test_open_matchday_form_uses_only_completed_matches_and_limits_to_ten():
    rows = [
        {"date": f"2026-08-{day:02d}", "home": "Club A", "away": "Club B",
         "ft_home": str(day % 3), "ft_away": "0"}
        for day in range(1, 13)
    ]
    rows.append({"date": "2026-08-13", "home": "Club A", "away": "Club C",
                 "ft_home": "", "ft_away": ""})
    form = _form("Club A", rows)
    assert form["matches_played"] == 10
    assert len(form["matches"]) == 10
    assert form["average_goals_scored"] is not None
    assert form["wins"] + form["draws"] + form["losses"] == 10



def test_open_matchday_form_summarizes_partial_match_statistics_without_zero_filling():
    rows = [
        {
            "date": "2026-08-01", "home": "Club A", "away": "Club B",
            "ft_home": "2", "ft_away": "1",
            "home_shots": "12", "away_shots": "7",
            "home_target": "5", "away_target": "3",
            "home_fouls": "10", "away_fouls": "14",
            "home_corners": "6", "away_corners": "2",
            "home_yellow": "2", "away_yellow": "3",
            "home_red": "0", "away_red": "0",
        },
        {
            "date": "2026-08-08", "home": "Club C", "away": "Club A",
            "ft_home": "0", "ft_away": "1",
            "home_shots": "", "away_shots": "",
            "home_target": "", "away_target": "",
            "home_fouls": "", "away_fouls": "",
            "home_corners": "4", "away_corners": "5",
            "home_yellow": "", "away_yellow": "",
            "home_red": "", "away_red": "",
        },
    ]

    form = _form("Club A", rows)
    assert form["statistics"]["shots"] == {
        "available": True, "matches_sampled": 1,
        "average_for": 12.0, "average_against": 7.0,
    }
    assert form["statistics"]["corners"] == {
        "available": True, "matches_sampled": 2,
        "average_for": 5.5, "average_against": 3.0,
    }
    assert form["statistics"]["shots_on_target"]["matches_sampled"] == 1
    assert form["statistics_note"].startswith("Averages use only matches")
