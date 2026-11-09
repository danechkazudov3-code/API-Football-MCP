from tools.backtesting import run_walk_forward_backtest


def _match(fid, day, home, away, hg, ag):
    return {
        "fixture": {"id": fid, "date": f"2025-01-{day:02d}T15:00:00+00:00",
                    "status": {"short": "FT"}},
        "league": {"id": 39},
        "teams": {"home": {"id": home}, "away": {"id": away}},
        "goals": {"home": hg, "away": ag},
    }


def test_walk_forward_backtest_uses_only_prior_fixtures():
    fixtures = [
        _match(1, 1, 1, 2, 2, 0),
        _match(2, 2, 3, 4, 1, 1),
        _match(3, 3, 1, 3, 1, 0),
        _match(4, 4, 2, 4, 0, 2),
        _match(5, 5, 1, 4, 2, 1),
        _match(6, 6, 2, 3, 1, 1),
        _match(7, 7, 1, 2, 1, 0),
    ]
    report = run_walk_forward_backtest(fixtures, min_history=2, history_window=5)
    assert report["success"] is True
    assert report["chronological_walk_forward"] is True
    assert report["fixtures_evaluated"] >= 1
    assert report["predictions"][-1]["fixture_id"] == 7
    assert 0 <= report["metrics"]["1x2_brier_score"] <= 2
    assert report["profitability_evaluated"] is False


def test_backtest_does_not_fabricate_metrics_without_enough_history():
    report = run_walk_forward_backtest([_match(1, 1, 1, 2, 1, 0)], min_history=5)
    assert report["status"] == "INSUFFICIENT_SAMPLE"
    assert report["fixtures_evaluated"] == 0


def test_backtest_rejects_invalid_history_settings():
    import pytest
    with pytest.raises(ValueError):
        run_walk_forward_backtest([], min_history=6, history_window=5)



def test_same_day_results_do_not_leak_into_other_same_day_forecasts(monkeypatch):
    import tools.backtesting as backtesting

    observed_home_averages = []

    def fake_forecast(home_form, away_form, *, league_baseline, home_advantage):
        observed_home_averages.append(home_form["average_goals_scored"])
        return {
            "available": True,
            "market_probabilities": {
                "home_win": 0.4, "draw": 0.3, "away_win": 0.3,
                "over_2_5": 0.5, "under_2_5": 0.5,
                "btts_yes": 0.5, "btts_no": 0.5,
            },
        }

    monkeypatch.setattr(backtesting, "forecast_from_recent_form", fake_forecast)
    fixtures = [
        _match(1, 1, 1, 2, 4, 0),  # Establishes prior history for team 1.
        _match(2, 2, 1, 3, 0, 3),
        _match(3, 2, 1, 4, 2, 0),
    ]

    report = backtesting.run_walk_forward_backtest(
        fixtures, min_history=1, history_window=5
    )

    assert report["fixtures_evaluated"] == 2
    # Both forecasts on day 2 must see only the day-1 result (4 goals scored).
    assert observed_home_averages == [4.0, 4.0]
