from tools.prediction import evaluate_candidate, select_primary_candidate


def test_odds_band_does_not_override_probability_when_status_and_ev_tie():
    low_odds = evaluate_candidate({
        "market": "1X2",
        "selection": "Home win",
        "odds": 1.30,
        "model_probability": 0.80,
        "no_vig_probability": 0.75,
    })
    preferred_odds = evaluate_candidate({
        "market": "Total goals 2.5",
        "selection": "Over 2.5",
        "odds": 1.90,
        "model_probability": 0.547368421,
        "no_vig_probability": 0.52,
    })

    assert low_odds["status"] == "LEAN"
    assert preferred_odds["status"] == "LEAN"
    assert low_odds["expected_value"] == preferred_odds["expected_value"]
    assert low_odds["odds_profile"] == "LOW_ODDS"
    assert preferred_odds["odds_profile"] == "PREFERRED"
    # With equal status and EV, model probability breaks the tie; odds bands do not.
    assert select_primary_candidate([low_odds, preferred_odds]) == low_odds


def test_high_odds_candidate_remains_visible_but_is_marked_high_variance():
    candidate = evaluate_candidate({
        "market": "1X2",
        "selection": "Away win",
        "odds": 4.20,
        "model_probability": 0.27,
        "no_vig_probability": 0.25,
    })

    assert candidate["odds_profile"] == "HIGH_VARIANCE"
    assert candidate["status"] == "LEAN"
