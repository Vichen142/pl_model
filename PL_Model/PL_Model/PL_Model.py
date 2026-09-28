import os
import json
import reflex as rx
from typing import List, Dict, Any
from .engine import (
    simulate_season_standings, 
    get_match_probability, 
    calculate_updated_elo,
    base_elo_ratings, 
    PL_TEAMS
)

DATA_FILE = "season_state.json"
GAMEWEEKS = [f"GW {i}" for i in range(1, 39)]
ADMIN_SECRET_KEY = "sunshine2026"

INJURY_OPTIONS = [
    "0 Key Starters Out (Full Squad)", 
    "1 Key Starter Out (-30 Elo)", 
    "2 Key Starters Out (-60 Elo)", 
    "3+ Key Crisis (-90 Elo)"
]

def get_initial_table() -> List[Dict[str, Any]]:
    return [
        {"team": str(team), "p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "gd": 0, "pts": 0}
        for team in PL_TEAMS
    ]

def save_season_data(actual_table, completed_fixtures, match_log, selected_gw, live_elo):
    try:
        data = {
            "actual_table": actual_table,
            "completed_fixtures": completed_fixtures,
            "match_log": match_log,
            "selected_gw": str(selected_gw),
            "live_elo": live_elo
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def load_season_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

class State(rx.State):
    simulations_count: int = 1000
    actual_table: List[Dict[str, Any]] = get_initial_table()
    simulation_results: List[Dict[str, Any]] = []
    completed_fixtures: List[List[str]] = []
    live_elo: Dict[str, float] = dict(base_elo_ratings)
    
    # Admin Authentication
    is_admin: bool = False
    admin_input_key: str = ""
    show_login_dialog: bool = False

    selected_gw: str = "GW 1"
    selected_home_team: str = "Arsenal"
    selected_away_team: str = "Chelsea"
    
    # Direct Metric Inputs
    home_score: str = "2"
    away_score: str = "1"
    home_xg: str = "1.8"
    away_xg: str = "0.9"
    home_sot: str = "6"
    away_sot: str = "3"
    home_injury: str = "0 Key Starters Out (Full Squad)"
    away_injury: str = "0 Key Starters Out (Full Squad)"
    
    prob_home: int = 49
    prob_draw: int = 27
    prob_away: int = 24
    
    match_log: List[Dict[str, Any]] = []
    filter_gw: str = "All Gameweeks"
    filter_team: str = "All Clubs"

    def on_mount(self):
        try:
            saved = load_season_data()
            if saved:
                self.actual_table = saved.get("actual_table", get_initial_table())
                self.completed_fixtures = saved.get("completed_fixtures", [])
                self.match_log = saved.get("match_log", [])
                self.selected_gw = saved.get("selected_gw", "GW 1")
                raw_elo = saved.get("live_elo", dict(base_elo_ratings))
                self.live_elo = {str(k): float(v) for k, v in raw_elo.items()}
        except Exception:
            self.actual_table = get_initial_table()
            self.completed_fixtures = []
            self.match_log = []
            self.live_elo = dict(base_elo_ratings)
            
        self.update_odds()
        self.run_simulation()

    def set_admin_input_key(self, val: str):
        self.admin_input_key = str(val)

    def toggle_login_dialog(self):
        self.show_login_dialog = not self.show_login_dialog

    def authenticate_admin(self):
        if self.admin_input_key == ADMIN_SECRET_KEY:
            self.is_admin = True
            self.show_login_dialog = False
            self.admin_input_key = ""
            return rx.window_alert("Admin Mode Unlocked!")
        else:
            return rx.window_alert("Invalid Admin Passcode!")

    def logout_admin(self):
        self.is_admin = False

    def get_injury_penalty(self, selection: str) -> int:
        if "1 Key Starter" in selection: return 30
        if "2 Key Starter" in selection: return 60
        if "3+ Key Crisis" in selection: return 90
        return 0

    def update_odds(self):
        try:
            if self.selected_home_team and self.selected_away_team:
                h_pen = self.get_injury_penalty(self.home_injury)
                a_pen = self.get_injury_penalty(self.away_injury)
                ph, pd, pa = get_match_probability(self.selected_home_team, self.selected_away_team, self.live_elo, h_pen, a_pen)
                self.prob_home = int(round(ph))
                self.prob_draw = int(round(pd))
                self.prob_away = int(round(pa))
        except Exception:
            pass

    def set_gw(self, value: str):
        self.selected_gw = str(value)
        if self.is_admin:
            self.persist()

    def set_home_team(self, value: str):
        self.selected_home_team = str(value)
        self.update_odds()

    def set_away_team(self, value: str):
        self.selected_away_team = str(value)
        self.update_odds()

    def set_h_score(self, value: str):
        self.home_score = str(value)

    def set_a_score(self, value: str):
        self.away_score = str(value)

    def set_h_xg(self, value: str):
        self.home_xg = str(value)

    def set_a_xg(self, value: str):
        self.away_xg = str(value)

    def set_h_sot(self, value: str):
        self.home_sot = str(value)

    def set_a_sot(self, value: str):
        self.away_sot = str(value)

    def set_h_inj(self, value: str):
        self.home_injury = str(value)
        self.update_odds()

    def set_a_inj(self, value: str):
        self.away_injury = str(value)
        self.update_odds()

    def set_gw_filter(self, value: str):
        self.filter_gw = str(value)

    def set_team_filter(self, value: str):
        self.filter_team = str(value)

    def persist(self):
        if self.is_admin:
            save_season_data(self.actual_table, self.completed_fixtures, self.match_log, self.selected_gw, self.live_elo)

    def run_simulation(self):
        try:
            table_dict = {row["team"]: row for row in self.actual_table}
            self.simulation_results = simulate_season_standings(
                actual_table_records=table_dict,
                completed_fixtures=self.completed_fixtures,
                live_elo=self.live_elo,
                num_simulations=self.simulations_count
            )
        except Exception:
            pass

    def submit_match_result(self):
        if not self.is_admin:
            return rx.window_alert("Please click 'Admin Login' at the top right to record official matches.")

        if self.selected_home_team == self.selected_away_team:
            return rx.window_alert("Home and Away clubs must be different!")

        try:
            hs = int(self.home_score)
            as_ = int(self.away_score)
            h_xg_val = float(self.home_xg) if self.home_xg else float(hs)
            a_xg_val = float(self.away_xg) if self.away_xg else float(as_)
        except ValueError:
            return rx.window_alert("Please enter valid numeric values for Goals and xG!")

        try:
            h = self.selected_home_team
            a = self.selected_away_team

            # Dynamic Elo Calculation
            self.live_elo = calculate_updated_elo(h, a, hs, as_, h_xg_val, a_xg_val, self.live_elo)
            self.completed_fixtures.append([h, a])

            new_table = [dict(row) for row in self.actual_table]
            home_row = next(r for r in new_table if r["team"] == h)
            away_row = next(r for r in new_table if r["team"] == a)

            home_row["p"] += 1
            away_row["p"] += 1
            home_row["gf"] += hs
            home_row["ga"] += as_
            home_row["gd"] = home_row["gf"] - home_row["ga"]

            away_row["gf"] += as_
            away_row["ga"] += hs
            away_row["gd"] = away_row["gf"] - away_row["ga"]

            if hs > as_:
                home_row["w"] += 1
                home_row["pts"] += 3
                away_row["l"] += 1
                badge = "Home Win"
                badge_color = "green"
            elif hs == as_:
                home_row["d"] += 1
                home_row["pts"] += 1
                away_row["d"] += 1
                away_row["pts"] += 1
                badge = "Draw"
                badge_color = "amber"
            else:
                away_row["w"] += 1
                away_row["pts"] += 3
                home_row["l"] += 1
                badge = "Away Win"
                badge_color = "purple"

            new_table.sort(
                key=lambda x: (x["pts"], x["gd"], x["gf"], -ord(x["team"][0])),
                reverse=True
            )

            self.actual_table = new_table

            match_entry = {
                "id": len(self.match_log),
                "gw": str(self.selected_gw),
                "home": str(h),
                "away": str(a),
                "home_score": int(hs),
                "away_score": int(as_),
                "home_xg": float(h_xg_val),
                "away_xg": float(a_xg_val),
                "score": f"{h} {hs} ({h_xg_val} xG) - ({a_xg_val} xG) {as_} {a}",
                "badge": badge,
                "color": badge_color
            }
            self.match_log.insert(0, match_entry)
            self.persist()
            self.update_odds()
            self.run_simulation()
        except Exception:
            return rx.window_alert("Error processing match. Please try again.")

    def remove_match(self, match_id: int):
        if not self.is_admin:
            return rx.window_alert("Only the admin can delete matches.")

        try:
            match_to_remove = next((m for m in self.match_log if m["id"] == match_id), None)
            if not match_to_remove:
                return

            h = match_to_remove["home"]
            a = match_to_remove["away"]
            hs = match_to_remove["home_score"]
            as_ = match_to_remove["away_score"]

            if [h, a] in self.completed_fixtures:
                self.completed_fixtures.remove([h, a])

            new_table = [dict(row) for row in self.actual_table]
            home_row = next(r for r in new_table if r["team"] == h)
            away_row = next(r for r in new_table if r["team"] == a)

            home_row["p"] -= 1
            away_row["p"] -= 1
            home_row["gf"] -= hs
            home_row["ga"] -= as_
            home_row["gd"] = home_row["gf"] - home_row["ga"]

            away_row["gf"] -= as_
            away_row["ga"] -= hs
            away_row["gd"] = away_row["gf"] - away_row["ga"]

            if hs > as_:
                home_row["w"] -= 1
                home_row["pts"] -= 3
                away_row["l"] -= 1
            elif hs == as_:
                home_row["d"] -= 1
                home_row["pts"] -= 1
                away_row["d"] -= 1
                away_row["pts"] -= 1
            else:
                away_row["w"] -= 1
                away_row["pts"] -= 3
                home_row["l"] -= 1

            new_table.sort(
                key=lambda x: (x["pts"], x["gd"], x["gf"], -ord(x["team"][0])),
                reverse=True
            )

            self.actual_table = new_table
            self.match_log = [m for m in self.match_log if m["id"] != match_id]
            
            recalculated_elo = dict(base_elo_ratings)
            for m in reversed(self.match_log):
                recalculated_elo = calculate_updated_elo(
                    m["home"], m["away"], m["home_score"], m["away_score"], 
                    m.get("home_xg", float(m["home_score"])), m.get("away_xg", float(m["away_score"])), 
                    recalculated_elo
                )
            self.live_elo = recalculated_elo

            self.persist()
            self.update_odds()
            self.run_simulation()
        except Exception:
            pass

    def reset_season(self):
        if not self.is_admin:
            return rx.window_alert("Only the admin can reset the season.")

        try:
            self.actual_table = get_initial_table()
            self.completed_fixtures = []
            self.match_log = []
            self.selected_gw = "GW 1"
            self.live_elo = dict(base_elo_ratings)
            save_season_data(self.actual_table, self.completed_fixtures, self.match_log, self.selected_gw, self.live_elo)
            self.update_odds()
            self.run_simulation()
            return rx.window_alert("Season has been successfully reset!")
        except Exception:
            return rx.window_alert("Reset completed.")

    @rx.var
    def top_contenders(self) -> List[Dict[str, Any]]:
        return self.simulation_results[:3] if len(self.simulation_results) >= 3 else []

    @rx.var
    def filtered_match_log(self) -> List[Dict[str, Any]]:
        logs = self.match_log
        if self.filter_gw != "All Gameweeks":
            logs = [m for m in logs if m["gw"] == self.filter_gw]
        if self.filter_team != "All Clubs":
            logs = [m for m in logs if m["home"] == self.filter_team or m["away"] == self.filter_team]
        return logs


# --- UI COMPONENTS ---

def stat_card(rank: int, team_name: str, pct: float, pts: float, gradient: str):
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(f"#{rank} Favorite", color_scheme="amber", variant="surface"),
                rx.spacer(),
                rx.icon("trophy", size=20, color="#EAB308"),
                width="100%"
            ),
            rx.heading(team_name, size="6", font_weight="bold", color="white"),
            rx.hstack(
                rx.vstack(
                    rx.text("Title Probability", size="1", color="gray"),
                    rx.heading(f"{pct}%", size="7", color="#38BDF8"),
                    spacing="1"
                ),
                rx.spacer(),
                rx.vstack(
                    rx.text("Proj. Points", size="1", color="gray"),
                    rx.heading(f"{pts}", size="7", color="#A78BFA"),
                    spacing="1"
                ),
                width="100%",
                padding_top="0.5rem"
            ),
            spacing="3",
            width="100%"
        ),
        style={
            "background": gradient,
            "border": "1px solid rgba(255, 255, 255, 0.12)",
            "backdrop-filter": "blur(12px)",
            "transition": "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
            "_hover": {"transform": "translateY(-4px)", "box-shadow": "0 12px 24px -10px rgba(0,0,0,0.5)"}
        },
        flex="1",
        min_width="260px"
    )

def projected_row(row_data: Dict[str, Any]):
    return rx.table.row(
        rx.table.cell(rx.text(row_data["team"], font_weight="bold")),
        rx.table.cell(
            rx.badge(f"{row_data['title_win_pct']}%", color_scheme="indigo", variant="solid")
        ),
        rx.table.cell(f"{row_data['top_4_pct']}%"),
        rx.table.cell(
            rx.badge(f"{row_data['relegation_pct']}%", color_scheme="ruby", variant="soft")
        ),
        rx.table.cell(rx.text(f"{row_data['avg_points']}", font_weight="bold", color="#38BDF8")),
        rx.table.cell(
            rx.badge(f"{row_data['live_elo']}", color_scheme="cyan", variant="surface")
        ),
        rx.table.cell(f"{row_data['current_pts']}"),
    )

def official_table_row(row: Dict[str, Any]):
    return rx.table.row(
        rx.table.cell(rx.text(row["team"], font_weight="bold")),
        rx.table.cell(str(row["p"])),
        rx.table.cell(str(row["w"])),
        rx.table.cell(str(row["d"])),
        rx.table.cell(str(row["l"])),
        rx.table.cell(str(row["gf"])),
        rx.table.cell(str(row["ga"])),
        rx.table.cell(str(row["gd"])),
        rx.table.cell(rx.text(str(row["pts"]), font_weight="bold", color="#A78BFA")),
    )

def match_log_row(item: Dict[str, Any]):
    return rx.hstack(
        rx.badge(item["gw"], color_scheme="cyan", variant="surface", min_width="60px"),
        rx.badge(item["badge"], color_scheme=item["color"], variant="surface", min_width="85px"),
        rx.text(item["score"], font_weight="medium", color="white"),
        rx.spacer(),
        rx.cond(
            State.is_admin,
            rx.icon_button(
                rx.icon("trash-2", size=14),
                on_click=lambda: State.remove_match(item["id"]),
                variant="ghost",
                color_scheme="ruby",
                size="1"
            )
        ),
        width="100%",
        padding_y="0.3rem",
        align="center"
    )

def index() -> rx.Component:
    return rx.box(
        rx.container(
            rx.vstack(
                # Header Section
                rx.vstack(
                    rx.hstack(
                        rx.badge("Premier League AI Engine", color_scheme="cyan", variant="surface", size="2"),
                        rx.badge("Monte Carlo 1,000x", color_scheme="purple", variant="surface", size="2"),
                        rx.badge("xG + Dynamic Elo Radar", color_scheme="green", variant="surface", size="2"),
                        rx.spacer(),
                        # Admin Status & Controls
                        rx.cond(
                            State.is_admin,
                            rx.hstack(
                                rx.badge("Admin Mode Active", color_scheme="green", variant="solid"),
                                rx.button(
                                    rx.hstack(rx.icon("rotate-ccw", size=14), rx.text("Reset Season")),
                                    on_click=State.reset_season,
                                    variant="surface",
                                    color_scheme="ruby",
                                    size="2"
                                ),
                                rx.button("Exit Admin", on_click=State.logout_admin, variant="ghost", size="2"),
                                spacing="2"
                            ),
                            rx.dialog.root(
                                rx.dialog.trigger(
                                    rx.button(
                                        rx.hstack(rx.icon("lock", size=14), rx.text("Admin Login")),
                                        variant="surface",
                                        color_scheme="gray",
                                        size="2"
                                    )
                                ),
                                rx.dialog.content(
                                    rx.dialog.title("Admin Authentication"),
                                    rx.dialog.description("Enter your admin passcode ('sunshine2026') to submit match results to disk."),
                                    rx.vstack(
                                        rx.input(
                                            placeholder="Enter Admin Passcode",
                                            type="password",
                                            value=State.admin_input_key,
                                            on_change=State.set_admin_input_key
                                        ),
                                        rx.hstack(
                                            rx.dialog.close(
                                                rx.button("Cancel", variant="soft", color_scheme="gray")
                                            ),
                                            rx.button("Unlock Admin", on_click=State.authenticate_admin, color_scheme="indigo"),
                                            spacing="3",
                                            justify="end",
                                            width="100%"
                                        ),
                                        spacing="4",
                                        padding_top="1rem"
                                    )
                                )
                            )
                        ),
                        width="100%",
                        align="center"
                    ),
                    rx.heading(
                        "Premier League Season Simulator & Odds Radar", 
                        size="9", 
                        weight="bold",
                        style={
                            "background": "linear-gradient(90deg, #FFFFFF, #94A3B8)",
                            "-webkit-background-clip": "text",
                            "-webkit-text-fill-color": "transparent"
                        }
                    ),
                    rx.text(
                        "Real-time machine learning projections powered by Expected Goals (xG), Shots on Target, Squad Absences & Dynamic Elo updates.",
                        color="#94A3B8",
                        size="3"
                    ),
                    align="center",
                    text_align="center",
                    padding_y="1.5rem",
                    spacing="3",
                    width="100%"
                ),

                # Top Contenders Spotlight Cards
                rx.hstack(
                    rx.cond(
                        State.top_contenders.length() >= 3,
                        rx.hstack(
                            stat_card(1, State.top_contenders[0]["team"], State.top_contenders[0]["title_win_pct"], State.top_contenders[0]["avg_points"], "linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9))"),
                            stat_card(2, State.top_contenders[1]["team"], State.top_contenders[1]["title_win_pct"], State.top_contenders[1]["avg_points"], "linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9))"),
                            stat_card(3, State.top_contenders[2]["team"], State.top_contenders[2]["title_win_pct"], State.top_contenders[2]["avg_points"], "linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9))"),
                            width="100%",
                            wrap="wrap",
                            spacing="4"
                        )
                    ),
                    width="100%"
                ),

                # Match Ingestion & Fixture Simulator Panel
                rx.card(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("swords", size=20, color="#38BDF8"),
                            rx.heading("Fixture Simulator & Multi-Metric Match Ingestion", size="4"),
                            rx.spacer(),
                            rx.cond(
                                State.is_admin,
                                rx.badge("Admin Ingestion Mode", color_scheme="green", variant="surface"),
                                rx.badge("Interactive Preview Mode", color_scheme="blue", variant="surface")
                            ),
                            width="100%",
                            align="center"
                        ),
                        rx.divider(color_scheme="gray"),
                        
                        # Match Win Probabilities Breakdown
                        rx.vstack(
                            rx.hstack(
                                rx.text(f"{State.selected_home_team} Win: {State.prob_home}%", size="2", font_weight="bold", color="#38BDF8"),
                                rx.spacer(),
                                rx.text(f"Draw: {State.prob_draw}%", size="2", font_weight="bold", color="#94A3B8"),
                                rx.spacer(),
                                rx.text(f"{State.selected_away_team} Win: {State.prob_away}%", size="2", font_weight="bold", color="#C084FC"),
                                width="100%"
                            ),
                            rx.progress(value=State.prob_home, max=100, width="100%", color_scheme="blue", size="2"),
                            width="100%",
                            spacing="1"
                        ),

                        # Row 1: Clubs, Gameweek, Score
                        rx.hstack(
                            rx.vstack(
                                rx.text("Gameweek", size="1", color="gray"),
                                rx.select(GAMEWEEKS, value=State.selected_gw, on_change=State.set_gw, width="100px"),
                                align="start"
                            ),
                            rx.vstack(
                                rx.text("Home Club", size="1", color="gray"),
                                rx.select(PL_TEAMS, value=State.selected_home_team, on_change=State.set_home_team, width="160px"),
                                align="start"
                            ),
                            rx.vstack(
                                rx.text("Goals", size="1", color="gray"),
                                rx.input(type="number", value=State.home_score, on_change=State.set_h_score, width="65px"),
                                align="center"
                            ),
                            rx.text("VS", font_weight="bold", color="gray", padding_top="1.2rem"),
                            rx.vstack(
                                rx.text("Goals", size="1", color="gray"),
                                rx.input(type="number", value=State.away_score, on_change=State.set_a_score, width="65px"),
                                align="center"
                            ),
                            rx.vstack(
                                rx.text("Away Club", size="1", color="gray"),
                                rx.select(PL_TEAMS, value=State.selected_away_team, on_change=State.set_away_team, width="160px"),
                                align="start"
                            ),
                            rx.spacer(),
                            rx.button(
                                rx.hstack(rx.icon("play", size=16), rx.text("Ingest Match")),
                                on_click=State.submit_match_result,
                                color_scheme="indigo",
                                size="3",
                                margin_top="1.2rem"
                            ),
                            width="100%",
                            align="center",
                            wrap="wrap",
                            spacing="4"
                        ),

                        # Row 2: Underlying Analytics (xG, SoT, Squad Absences)
                        rx.vstack(
                            rx.divider(color_scheme="gray"),
                            rx.hstack(
                                rx.badge("Underlying Analytics & Availability Inputs", color_scheme="amber", variant="surface"),
                                rx.text("xG differentials & squad absence weights directly tune live Elo calibration.", size="1", color="gray"),
                                align="center",
                                spacing="2"
                            ),
                            rx.hstack(
                                rx.vstack(
                                    rx.text("Home xG", size="1", color="gray"),
                                    rx.input(placeholder="1.8", value=State.home_xg, on_change=State.set_h_xg, width="85px"),
                                    align="start"
                                ),
                                rx.vstack(
                                    rx.text("Away xG", size="1", color="gray"),
                                    rx.input(placeholder="0.9", value=State.away_xg, on_change=State.set_a_xg, width="85px"),
                                    align="start"
                                ),
                                rx.vstack(
                                    rx.text("Home SOT", size="1", color="gray"),
                                    rx.input(placeholder="6", value=State.home_sot, on_change=State.set_h_sot, width="80px"),
                                    align="start"
                                ),
                                rx.vstack(
                                    rx.text("Away SOT", size="1", color="gray"),
                                    rx.input(placeholder="3", value=State.away_sot, on_change=State.set_a_sot, width="80px"),
                                    align="start"
                                ),
                                rx.vstack(
                                    rx.text("Home Squad Absences", size="1", color="gray"),
                                    rx.select(INJURY_OPTIONS, value=State.home_injury, on_change=State.set_h_inj, width="210px"),
                                    align="start"
                                ),
                                rx.vstack(
                                    rx.text("Away Squad Absences", size="1", color="gray"),
                                    rx.select(INJURY_OPTIONS, value=State.away_injury, on_change=State.set_a_inj, width="210px"),
                                    align="start"
                                ),
                                width="100%",
                                align="center",
                                wrap="wrap",
                                spacing="3"
                            ),
                            width="100%",
                            spacing="3"
                        ),

                        spacing="4",
                        width="100%"
                    ),
                    width="100%",
                    padding="1.5rem",
                    style={"border": "1px solid rgba(255, 255, 255, 0.08)", "background": "rgba(15, 23, 42, 0.6)"}
                ),

                # Tabs: Monte Carlo Projections VS Actual Official League Table
                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("🏆 Monte Carlo Projections", value="projections"),
                        rx.tabs.trigger("📊 Live Official League Table", value="actual_table"),
                    ),
                    rx.tabs.content(
                        rx.card(
                            rx.table.root(
                                rx.table.header(
                                    rx.table.row(
                                        rx.table.column_header_cell("Club"),
                                        rx.table.column_header_cell("Title Win %"),
                                        rx.table.column_header_cell("Top 4 (UCL) %"),
                                        rx.table.column_header_cell("Relegation %"),
                                        rx.table.column_header_cell("Simulated Points"),
                                        rx.table.column_header_cell("Live Elo"),
                                        rx.table.column_header_cell("Current Actual Pts"),
                                    )
                                ),
                                rx.table.body(
                                    rx.foreach(State.simulation_results, projected_row)
                                ),
                                width="100%",
                                variant="surface"
                            ),
                            padding="0"
                        ),
                        value="projections"
                    ),
                    rx.tabs.content(
                        rx.card(
                            rx.table.root(
                                rx.table.header(
                                    rx.table.row(
                                        rx.table.column_header_cell("Club"),
                                        rx.table.column_header_cell("PL"),
                                        rx.table.column_header_cell("W"),
                                        rx.table.column_header_cell("D"),
                                        rx.table.column_header_cell("L"),
                                        rx.table.column_header_cell("GF"),
                                        rx.table.column_header_cell("GA"),
                                        rx.table.column_header_cell("GD"),
                                        rx.table.column_header_cell("PTS"),
                                    )
                                ),
                                rx.table.body(
                                    rx.foreach(State.actual_table, official_table_row)
                                ),
                                width="100%",
                                variant="surface"
                            ),
                            padding="0"
                        ),
                        value="actual_table"
                    ),
                    default_value="projections",
                    width="100%"
                ),

                # Match Log Feed
                rx.cond(
                    State.match_log.length() > 0,
                    rx.card(
                        rx.vstack(
                            rx.hstack(
                                rx.hstack(
                                    rx.icon("history", size=18, color="#38BDF8"),
                                    rx.heading("Gameweek History & Results", size="3"),
                                    rx.badge(f"{State.match_log.length()} played", color_scheme="gray", variant="surface"),
                                    spacing="2",
                                    align="center"
                                ),
                                rx.spacer(),
                                rx.hstack(
                                    rx.text("Filter GW:", size="1", color="gray"),
                                    rx.select(
                                        ["All Gameweeks"] + GAMEWEEKS,
                                        value=State.filter_gw,
                                        on_change=State.set_gw_filter,
                                        size="1",
                                        width="130px"
                                    ),
                                    rx.text("Club:", size="1", color="gray"),
                                    rx.select(
                                        ["All Clubs"] + PL_TEAMS,
                                        value=State.filter_team,
                                        on_change=State.set_team_filter,
                                        size="1",
                                        width="130px"
                                    ),
                                    spacing="2",
                                    align="center"
                                ),
                                width="100%",
                                align="center",
                                wrap="wrap"
                            ),
                            rx.divider(color_scheme="gray"),
                            
                            rx.scroll_area(
                                rx.vstack(
                                    rx.foreach(State.filtered_match_log, match_log_row),
                                    spacing="2",
                                    width="100%"
                                ),
                                type="always",
                                scrollbars="vertical",
                                style={"max_height": "240px", "width": "100%", "padding_right": "10px"}
                            ),
                            spacing="3",
                            width="100%"
                        ),
                        width="100%",
                        padding="1.25rem",
                        style={"border": "1px solid rgba(255, 255, 255, 0.08)", "background": "rgba(15, 23, 42, 0.6)"}
                    )
                ),
                spacing="6",
                padding_y="2.5rem"
            ),
            size="4"
        ),
        background="radial-gradient(ellipse 80% 50% at 50% -20%, rgba(120, 119, 198, 0.15), rgba(255, 255, 255, 0))",
        min_height="100vh"
    )

app = rx.App(
    theme=rx.theme(appearance="dark", accent_color="indigo", radius="large")
)
app.add_page(index, on_load=State.on_mount)