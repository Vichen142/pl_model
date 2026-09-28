import os
import math
import joblib
import numpy as np
import pandas as pd

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)

def find_file(filename: str) -> str:
    p1 = os.path.join(PARENT_DIR, filename)
    p2 = os.path.join(CURRENT_DIR, filename)
    p3 = filename
    if os.path.exists(p1): return p1
    if os.path.exists(p2): return p2
    return p3

model = joblib.load(find_file('epl_rf_model.pkl'))
feature_cols = joblib.load(find_file('feature_cols.pkl'))
base_elo_ratings = joblib.load(find_file('current_elo_ratings.pkl'))

# Ensure all base elo values are standard python floats
base_elo_ratings = {str(k): float(v) for k, v in base_elo_ratings.items()}

PL_TEAMS = [
    'Arsenal', 'Aston Villa', 'Bournemouth', 'Brentford', 'Brighton', 
    'Chelsea', 'Crystal Palace', 'Everton', 'Fulham', 'Ipswich', 
    'Leicester', 'Liverpool', 'Man City', 'Man United', 'Newcastle', 
    "Nott'm Forest", 'Southampton', 'Tottenham', 'West Ham', 'Wolves'
]

def calculate_updated_elo(home_team: str, away_team: str, hs: int, as_: int, 
                          h_xg: float, a_xg: float, current_elo: dict, k: int = 20) -> dict:
    h_elo = float(current_elo.get(home_team, 1500.0))
    a_elo = float(current_elo.get(away_team, 1500.0))
    
    e_home = 1.0 / (1.0 + math.pow(10, (a_elo - (h_elo + 65.0)) / 400.0))
    e_away = 1.0 - e_home
    
    if hs > as_:
        s_home, s_away = 1.0, 0.0
    elif hs == as_:
        s_home, s_away = 0.5, 0.5
    else:
        s_home, s_away = 0.0, 1.0
        
    actual_gd = float(hs - as_)
    xg_gd = float(h_xg - a_xg)
    blended_gd = (actual_gd * 0.6) + (xg_gd * 0.4)
    margin_mult = math.sqrt(abs(blended_gd)) if abs(blended_gd) > 1.0 else 1.0
    
    delta_home = k * margin_mult * (s_home - e_home)
    delta_away = k * margin_mult * (s_away - e_away)
    
    updated = {str(k_): float(v_) for k_, v_ in current_elo.items()}
    updated[home_team] = round(float(h_elo + delta_home), 1)
    updated[away_team] = round(float(a_elo + delta_away), 1)
    return updated

def get_match_probability(home_team: str, away_team: str, current_elo: dict = None,
                          home_injury_penalty: int = 0, away_injury_penalty: int = 0):
    if current_elo is None:
        current_elo = base_elo_ratings
        
    h_elo = float(current_elo.get(home_team, 1500.0)) - float(home_injury_penalty)
    a_elo = float(current_elo.get(away_team, 1500.0)) - float(away_injury_penalty)
    
    match_features = pd.DataFrame([{
        'Elo_Diff': (h_elo + 65.0) - a_elo,
        'Home_PreMatch_Elo': h_elo,
        'Away_PreMatch_Elo': a_elo,
        'Home_Rolling_Points_Last5': 1.5,
        'Home_Rolling_GoalsScored_Last5': 1.4,
        'Home_Rolling_SOT_Last5': 4.5,
        'Away_Rolling_Points_Last5': 1.2,
        'Away_Rolling_GoalsScored_Last5': 1.1,
        'Away_Rolling_SOT_Last5': 3.8,
        'Home_Rolling_Points_Last15': 1.5,
        'Away_Rolling_Points_Last15': 1.2
    }])
    
    probs = model.predict_proba(match_features)[0]
    classes = list(model.classes_)
    p_home = round(float(probs[classes.index('H')]) * 100.0, 1) if 'H' in classes else 33.3
    p_draw = round(float(probs[classes.index('D')]) * 100.0, 1) if 'D' in classes else 33.3
    p_away = round(float(probs[classes.index('A')]) * 100.0, 1) if 'A' in classes else 33.3
    return float(p_home), float(p_draw), float(p_away)

def simulate_season_standings(actual_table_records: dict, completed_fixtures: list = None, 
                              live_elo: dict = None, num_simulations=1000):
    if completed_fixtures is None:
        completed_fixtures = []
    if live_elo is None:
        live_elo = base_elo_ratings
        
    completed_set = set(tuple(f) for f in completed_fixtures)
    all_fixtures = [(h, a) for h in PL_TEAMS for a in PL_TEAMS if h != a]
    remaining_fixtures = [f for f in all_fixtures if f not in completed_set]
    
    fixture_probs = {}
    for home, away in remaining_fixtures:
        h_elo = float(live_elo.get(home, 1500.0))
        a_elo = float(live_elo.get(away, 1500.0))
        
        match_features = pd.DataFrame([{
            'Elo_Diff': (h_elo + 65.0) - a_elo,
            'Home_PreMatch_Elo': h_elo,
            'Away_PreMatch_Elo': a_elo,
            'Home_Rolling_Points_Last5': 1.5,
            'Home_Rolling_GoalsScored_Last5': 1.4,
            'Home_Rolling_SOT_Last5': 4.5,
            'Away_Rolling_Points_Last5': 1.2,
            'Away_Rolling_GoalsScored_Last5': 1.1,
            'Away_Rolling_SOT_Last5': 3.8,
            'Home_Rolling_Points_Last15': 1.5,
            'Away_Rolling_Points_Last15': 1.2
        }])
        
        probs = model.predict_proba(match_features)[0]
        classes = list(model.classes_)
        fixture_probs[(home, away)] = {
            'H': float(probs[classes.index('H')]),
            'D': float(probs[classes.index('D')]),
            'A': float(probs[classes.index('A')])
        }
        
    title_wins = {t: 0 for t in PL_TEAMS}
    top_4_finishes = {t: 0 for t in PL_TEAMS}
    relegated = {t: 0 for t in PL_TEAMS}
    total_points = {t: 0.0 for t in PL_TEAMS}
    
    current_pts_map = {t: int(actual_table_records.get(t, {}).get('pts', 0)) for t in PL_TEAMS}
    current_gd_map = {t: int(actual_table_records.get(t, {}).get('gd', 0)) for t in PL_TEAMS}
    
    for _ in range(num_simulations):
        sim_table = current_pts_map.copy()
        for h, a in remaining_fixtures:
            p = fixture_probs[(h, a)]
            outcome = np.random.choice(['H', 'D', 'A'], p=[p['H'], p['D'], p['A']])
            if outcome == 'H': 
                sim_table[h] += 3
            elif outcome == 'D': 
                sim_table[h] += 1
                sim_table[a] += 1
            else: 
                sim_table[a] += 3
            
        ranked = sorted(sim_table.items(), key=lambda x: (x[1], current_gd_map.get(x[0], 0)), reverse=True)
        title_wins[ranked[0][0]] += 1
        for r, (t, pts) in enumerate(ranked):
            total_points[t] += float(pts)
            if r < 4: top_4_finishes[t] += 1
            if r >= 17: relegated[t] += 1
            
    summary = []
    for team in PL_TEAMS:
        summary.append({
            "team": str(team),
            "title_win_pct": float(round((title_wins[team] / num_simulations) * 100.0, 1)),
            "top_4_pct": float(round((top_4_finishes[team] / num_simulations) * 100.0, 1)),
            "relegation_pct": float(round((relegated[team] / num_simulations) * 100.0, 1)),
            "avg_points": float(round(total_points[team] / num_simulations, 1)),
            "current_pts": int(current_pts_map[team]),
            "live_elo": float(round(live_elo.get(team, 1500.0), 1))
        })
        
    return sorted(summary, key=lambda x: (x['title_win_pct'], x['avg_points']), reverse=True)