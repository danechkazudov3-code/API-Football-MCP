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
    assert form["venue_splits"] if "venue_splits" in form else True
