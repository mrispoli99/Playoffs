import streamlit as st
import pandas as pd
import requests
import base64
import json
import io
from datetime import datetime

st.set_page_config(
    page_title="2026 NBA Playoff Bracket Challenge",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION — fill these in via Streamlit secrets (see README)
# ══════════════════════════════════════════════════════════════════════════════
# In Streamlit Cloud: Settings → Secrets, add:
#   GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"
#   GITHUB_REPO  = "yourname/your-repo"       e.g. "jsmith/nba-bracket-2026"
#   GITHUB_PATH  = "picks.xlsx"               path inside the repo

def get_cfg(key: str, fallback: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, fallback)

import os
GITHUB_TOKEN = get_cfg("GITHUB_TOKEN")
GITHUB_REPO  = get_cfg("GITHUB_REPO")   # e.g. "jsmith/nba-bracket-2026"
GITHUB_PATH  = get_cfg("GITHUB_PATH", "picks.xlsx")

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

# ══════════════════════════════════════════════════════════════════════════════
# STATIC BRACKET STRUCTURE  (teams / seeds only — scores come from ESPN)
# ══════════════════════════════════════════════════════════════════════════════

EAST_R1 = [
    {"id": "e1", "seed1": 1, "team1": "Pistons",   "seed2": 8, "team2": "Magic"},
    {"id": "e2", "seed1": 2, "team1": "Celtics",   "seed2": 7, "team2": "76ers"},
    {"id": "e3", "seed1": 3, "team1": "Knicks",    "seed2": 6, "team2": "Hawks"},
    {"id": "e4", "seed1": 4, "team1": "Cavaliers", "seed2": 5, "team2": "Raptors"},
]
WEST_R1 = [
    {"id": "w1", "seed1": 1, "team1": "Thunder",      "seed2": 8, "team2": "Suns"},
    {"id": "w2", "seed1": 2, "team1": "Spurs",        "seed2": 7, "team2": "Trail Blazers"},
    {"id": "w3", "seed1": 3, "team1": "Nuggets",      "seed2": 6, "team2": "Timberwolves"},
    {"id": "w4", "seed1": 4, "team1": "Lakers",       "seed2": 5, "team2": "Rockets"},
]
ALL_MATCHUPS = EAST_R1 + WEST_R1
SERIES_LENGTHS = ["4-0", "4-1", "4-2", "4-3"]

# ESPN short name → our team name (add more as rounds progress)
ESPN_NAME_MAP = {
    "Detroit":      "Pistons",
    "Orlando":      "Magic",
    "Boston":       "Celtics",
    "Philadelphia": "76ers",
    "NY Knicks":    "Knicks",
    "Atlanta":      "Hawks",
    "Cleveland":    "Cavaliers",
    "Toronto":      "Raptors",
    "OKC":          "Thunder",
    "Phoenix":      "Suns",
    "San Antonio":  "Spurs",
    "Portland":     "Trail Blazers",
    "Denver":       "Nuggets",
    "Minnesota":    "Timberwolves",
    "LA Lakers":    "Lakers",
    "Houston":      "Rockets",
}

# ══════════════════════════════════════════════════════════════════════════════
# LIVE SCORES  — ESPN undocumented scoreboard API (no key needed)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)   # refresh every 5 minutes
def fetch_playoff_series() -> dict:
    """
    Returns dict keyed by frozenset of team names:
      { frozenset({"Knicks","Hawks"}): {"leader": "Knicks", "score": "2-0", "complete": False}, ... }

    Strategy:
      1. Try ESPN's playoff series summary endpoint — gives cumulative series wins directly.
      2. Fall back to building series records by aggregating the scoreboard game-by-game.
    """
    series_data = {}

    # ── Attempt 1: playoff bracket / series endpoint ──────────────────────────
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/playoff-brackets"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            data = r.json()
            for series in data.get("series", []):
                competitors = series.get("competitors", [])
                if len(competitors) != 2:
                    continue
                wins = {}
                for c in competitors:
                    raw   = c.get("team", {}).get("shortDisplayName") or c.get("team", {}).get("displayName", "")
                    tname = ESPN_NAME_MAP.get(raw, raw)
                    wins[tname] = int(c.get("wins", 0) or 0)

                teams = list(wins.keys())
                if len(teams) != 2:
                    continue
                t1, t2 = teams
                w1, w2 = wins[t1], wins[t2]
                _store_series(series_data, t1, t2, w1, w2)

            if series_data:
                return series_data
    except Exception:
        pass

    # ── Attempt 2: aggregate game-by-game from scoreboard (multiple dates) ────
    try:
        from datetime import date, timedelta

        # Only count games between teams in our known bracket matchups
        VALID_SERIES_KEYS = {frozenset([m["team1"], m["team2"]]) for m in ALL_MATCHUPS}

        # Playoffs started April 18, 2026 — don't look at earlier games
        PLAYOFFS_START = date(2026, 4, 18)
        today = date.today()

        game_wins: dict = {}
        seen_game_ids: set = set()

        d = today
        while d >= PLAYOFFS_START:
            url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
            params = {"seasontype": 3, "dates": d.strftime("%Y%m%d")}
            r = requests.get(url, params=params, timeout=8)
            if r.status_code != 200:
                d -= timedelta(days=1)
                continue
            data = r.json()

            for event in data.get("events", []):
                game_id = event.get("id")
                if game_id in seen_game_ids:
                    continue

                status = event.get("status", {}).get("type", {}).get("completed", False)
                if not status:
                    continue

                comp = event["competitions"][0]
                competitors = comp.get("competitors", [])
                if len(competitors) != 2:
                    continue

                team_names, winner = [], None
                for c in competitors:
                    raw   = c["team"].get("shortDisplayName") or c["team"].get("displayName", "")
                    tname = ESPN_NAME_MAP.get(raw, raw)
                    team_names.append(tname)
                    if c.get("winner"):
                        winner = tname

                if len(team_names) != 2 or not winner:
                    continue

                # Only count games that are part of a known playoff series
                series_key = frozenset(team_names)
                if series_key not in VALID_SERIES_KEYS:
                    continue

                seen_game_ids.add(game_id)
                if series_key not in game_wins:
                    game_wins[series_key] = {team_names[0]: 0, team_names[1]: 0}
                if winner in game_wins[series_key]:
                    game_wins[series_key][winner] += 1

            d -= timedelta(days=1)

        for key, wins in game_wins.items():
            teams = list(wins.keys())
            t1, t2 = teams[0], teams[1]
            _store_series(series_data, t1, t2, wins[t1], wins[t2])

    except Exception:
        pass

    return series_data


def _store_series(series_data: dict, t1: str, t2: str, w1: int, w2: int):
    """Helper to compute leader/score/complete and store in series_data."""
    complete = (w1 == 4 or w2 == 4)
    if w1 == 0 and w2 == 0:
        score_str, leader = "0-0", None
    elif w1 >= w2:
        score_str, leader = f"{w1}-{w2}", t1
    else:
        score_str, leader = f"{w2}-{w1}", t2

    series_data[frozenset([t1, t2])] = {
        "leader":   leader,
        "score":    score_str,
        "complete": complete,
        "winner":   leader if complete else None,
    }


def enrich_matchups(matchups: list, series: dict) -> list:
    """Attach live result/score to each matchup dict."""
    enriched = []
    for m in matchups:
        key = frozenset([m["team1"], m["team2"]])
        live = series.get(key, {})
        enriched.append({
            **m,
            "result":   live.get("winner"),
            "score":    live.get("score"),
            "leader":   live.get("leader"),
            "complete": live.get("complete", False),
        })
    return enriched


# ══════════════════════════════════════════════════════════════════════════════
# GITHUB EXCEL STORAGE
# ══════════════════════════════════════════════════════════════════════════════

def _gh_get_file():
    """Returns (content_bytes, sha) or (None, None) if file doesn't exist."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"])
    return content, data["sha"]


def load_all_picks() -> dict:
    """Load picks from GitHub Excel. Returns dict keyed by user_key."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return _local_load()
    try:
        content, sha = _gh_get_file()
        if content is None:
            return {}
        df = pd.read_excel(io.BytesIO(content), sheet_name="picks", dtype=str)
        df = df.where(pd.notna(df), None)
        picks = {}
        for _, row in df.iterrows():
            ukey = row["user_key"]
            if not ukey:
                continue
            picks[ukey] = {
                "display_name": row.get("display_name", ukey),
                "locked":       row.get("locked", "False") == "True",
                "locked_at":    row.get("locked_at"),
                "updated_at":   row.get("updated_at"),
                "desired":      json.loads(row["desired"])   if row.get("desired")   else {},
                "predicted":    json.loads(row["predicted"]) if row.get("predicted") else {},
            }
        return picks
    except Exception as e:
        st.warning(f"Could not load from GitHub: {e}. Using local fallback.")
        return _local_load()


def save_all_picks(picks: dict):
    """Save picks dict back to GitHub as Excel."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        _local_save(picks)
        return
    try:
        rows = []
        for ukey, ud in picks.items():
            rows.append({
                "user_key":     ukey,
                "display_name": ud.get("display_name", ukey),
                "locked":       str(ud.get("locked", False)),
                "locked_at":    ud.get("locked_at", ""),
                "updated_at":   ud.get("updated_at", ""),
                "desired":      json.dumps(ud.get("desired",   {})),
                "predicted":    json.dumps(ud.get("predicted", {})),
            })
        df = pd.DataFrame(rows)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="picks", index=False)
            # Add a human-readable summary sheet
            _write_summary_sheet(writer, picks)
        buf.seek(0)

        _, sha = _gh_get_file()
        payload = {
            "message": f"Update picks — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "content": base64.b64encode(buf.read()).decode(),
        }
        if sha:
            payload["sha"] = sha

        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
        r = requests.put(url, headers=HEADERS, json=payload, timeout=15)
        r.raise_for_status()
    except Exception as e:
        st.error(f"GitHub save failed: {e}. Saving locally as fallback.")
        _local_save(picks)


def _write_summary_sheet(writer, picks: dict):
    """Write a human-friendly sheet for easy viewing in Excel."""
    rows = []
    for ukey, ud in picks.items():
        for mode in ("desired", "predicted"):
            p = ud.get(mode, {})
            row = {
                "Name":   ud.get("display_name", ukey),
                "Mode":   mode.capitalize(),
                "Locked": ud.get("locked", False),
            }
            for m in ALL_MATCHUPS:
                col = f"{m['team1'].split()[-1]}/{m['team2'].split()[-1]}"
                w = p.get(f"{m['id']}_winner", "")
                g = p.get(f"{m['id']}_games", "")
                row[col] = f"{w} ({g})" if w and g else w or ""
            row["Champion"] = p.get("finals_winner", "")
            row["Champ in"] = p.get("finals_games", "")
            rows.append(row)
    if rows:
        pd.DataFrame(rows).to_excel(writer, sheet_name="summary", index=False)


# Local JSON fallback (used when GitHub secrets not configured)
LOCAL_FILE = "picks_local.json"

def _local_load() -> dict:
    if os.path.exists(LOCAL_FILE):
        with open(LOCAL_FILE) as f:
            return json.load(f)
    return {}

def _local_save(picks: dict):
    with open(LOCAL_FILE, "w") as f:
        json.dump(picks, f, indent=2)


def user_key(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
.main .block-container { padding-top: 1.5rem; max-width: 1120px; }

.page-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%);
    border-radius: 14px; padding: 26px 30px; margin-bottom: 20px;
}
.page-header h1 { margin:0; font-size:26px; font-weight:700; color:white; }
.page-header p  { margin:6px 0 0; font-size:13px; color:#99aacc; }

.matchup-box {
    border: 1px solid #e4e4e4; border-radius: 10px;
    overflow: hidden; margin-bottom: 6px; background: #fafafa;
}
.matchup-label {
    font-size: 10px; font-weight: 700; color: #bbb;
    padding: 5px 11px 3px; background: white;
    border-bottom: 1px solid #f0f0f0; text-transform: uppercase; letter-spacing: .06em;
    display: flex; align-items: center; gap: 6px;
}
.team-row {
    display: flex; align-items: center; padding: 7px 11px; gap: 7px;
    border-bottom: 1px solid #f2f2f2; font-size: 13px;
}
.team-row:last-child { border-bottom: none; }
.team-row.series-leader { background: #eef6ff; }
.team-row.series-winner { background: #e8f5e9; font-weight: 600; }
.seed { font-size:10px; font-weight:700; color:#bbb; min-width:14px; }

.score-pill {
    font-size: 10px; padding: 2px 7px; border-radius: 20px; font-weight: 700;
    margin-left: auto;
}
.score-pill.live     { background:#fff3cd; color:#856404; }
.score-pill.complete { background:#d1e7dd; color:#0a3622; }
.score-pill.upcoming { background:#f0f0f0; color:#888; }

.locked-banner { background:#fff3e0; border:1px solid #ffcc80; border-radius:8px;
                 padding:9px 14px; font-size:13px; color:#bf360c; margin-bottom:12px; }
.section-title { font-size:12px; font-weight:700; color:#555;
                 text-transform:uppercase; letter-spacing:.08em; margin:16px 0 8px; }
.conf-title    { font-size:11px; font-weight:700; color:#999;
                 text-transform:uppercase; letter-spacing:.08em; margin-bottom:8px; }
.score-note    { font-size:11px; color:#888; margin-bottom:12px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="page-header">
  <h1>🏀 2026 NBA Playoff Bracket Challenge</h1>
  <p>Pick your <b>Desired Outcome ❤️</b> (who you <i>want</i> to win) and
     <b>Predicted Outcome 🧠</b> (who you <i>think</i> will win) — including series length.
     Scores update automatically every 5 minutes.</p>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# FETCH LIVE SCORES  (shown at top, used to enrich matchups)
# ══════════════════════════════════════════════════════════════════════════════

with st.spinner("Fetching live series scores…"):
    live_series = fetch_playoff_series()

east_r1 = enrich_matchups(EAST_R1, live_series)
west_r1 = enrich_matchups(WEST_R1, live_series)
all_matchups_live = east_r1 + west_r1

now_dt  = datetime.utcnow()
now_str = f"{now_dt.hour % 12 or 12}:{now_dt.minute:02d} {'AM' if now_dt.hour < 12 else 'PM'} UTC"
if live_series:
    st.markdown(
        f"<p class='score-note'>🟢 Live scores loaded — auto-refreshes every 5 min "
        f"(last fetched ~{now_str}). "
        f"<a href='javascript:window.location.reload()'>Refresh now</a></p>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<p class='score-note'>⚠️ Could not reach ESPN — showing bracket without live scores.</p>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# SERIES PICK WIDGET
# ══════════════════════════════════════════════════════════════════════════════

def series_pick_widget(matchup: dict, prefix: str, existing: dict, disabled: bool):
    mid = matchup["id"]
    t1, t2 = matchup["team1"], matchup["team2"]
    s1, s2 = matchup["seed1"], matchup["seed2"]
    leader   = matchup.get("leader")
    score    = matchup.get("score")
    complete = matchup.get("complete", False)

    # Row styling
    if complete:
        t1_cls = "team-row series-winner" if leader == t1 else "team-row"
        t2_cls = "team-row series-winner" if leader == t2 else "team-row"
        pill_cls, pill_txt = "score-pill complete", f"Final: {score}"
    elif leader and score and score != "0-0":
        t1_cls = "team-row series-leader" if leader == t1 else "team-row"
        t2_cls = "team-row series-leader" if leader == t2 else "team-row"
        pill_cls, pill_txt = "score-pill live", f"Series: {score}"
    else:
        t1_cls = t2_cls = "team-row"
        pill_cls, pill_txt = "score-pill upcoming", "Not started"

    st.markdown(f"""
    <div class="matchup-box">
      <div class="matchup-label">
        ({s1}) {t1} vs ({s2}) {t2}
        <span class="{pill_cls}" style="margin-left:auto">{pill_txt}</span>
      </div>
      <div class="{t1_cls}"><span class="seed">{s1}</span> {t1}</div>
      <div class="{t2_cls}"><span class="seed">{s2}</span> {t2}</div>
    </div>
    """, unsafe_allow_html=True)

    ex_winner = existing.get(f"{mid}_winner")
    ex_games  = existing.get(f"{mid}_games")

    winner_opts = ["— winner —", t1, t2]
    games_opts  = ["— games —"] + SERIES_LENGTHS

    w_idx = winner_opts.index(ex_winner) if ex_winner in winner_opts else 0
    g_idx = games_opts.index(ex_games)   if ex_games  in games_opts  else 0

    c1, c2 = st.columns([3, 2])
    with c1:
        winner = st.selectbox("Winner", winner_opts, index=w_idx,
                              key=f"{prefix}_{mid}_w", disabled=disabled,
                              label_visibility="collapsed")
    with c2:
        games = st.selectbox("In", games_opts, index=g_idx,
                             key=f"{prefix}_{mid}_g", disabled=disabled,
                             label_visibility="collapsed")

    w_val = winner if winner != "— winner —" else None
    g_val = games  if games  != "— games —"  else None
    summary = f"{w_val} in {g_val}" if w_val and g_val else None
    return w_val, g_val, summary


# ══════════════════════════════════════════════════════════════════════════════
# RENDER ONE FULL BRACKET (desired or predicted)
# ══════════════════════════════════════════════════════════════════════════════

def render_bracket_mode(mode_key, mode_label, mode_color, existing, is_locked, username, ukey):
    disabled = is_locked
    new_picks = {}

    st.markdown(
        f"<p style='font-size:13px;color:{mode_color};margin-bottom:4px;font-weight:600;'>"
        f"{'Who you want to win each series' if mode_key=='desired' else 'Who you think will actually win'}"
        f" — and in how many games.</p>",
        unsafe_allow_html=True,
    )

    # ── Round 1 ───────────────────────────────────────────────────────────────
    st.markdown("<div class='section-title'>First Round</div>", unsafe_allow_html=True)
    col_e, col_w = st.columns(2)

    with col_e:
        st.markdown("<div class='conf-title'>Eastern Conference</div>", unsafe_allow_html=True)
        for m in east_r1:
            w, g, s = series_pick_widget(m, mode_key, existing, disabled)
            new_picks[f"{m['id']}_winner"] = w
            new_picks[f"{m['id']}_games"]  = g
            if s: st.caption(f"📝 {s}")

    with col_w:
        st.markdown("<div class='conf-title'>Western Conference</div>", unsafe_allow_html=True)
        for m in west_r1:
            w, g, s = series_pick_widget(m, mode_key, existing, disabled)
            new_picks[f"{m['id']}_winner"] = w
            new_picks[f"{m['id']}_games"]  = g
            if s: st.caption(f"📝 {s}")

    # ── Semis  (1v8 winner plays 4v5 winner; 2v7 winner plays 3v6 winner) ────
    st.markdown("<div class='section-title'>Conference Semifinals</div>", unsafe_allow_html=True)

    esf_pairs = [
        ("esf1", new_picks.get("e1_winner") or "TBD", new_picks.get("e4_winner") or "TBD"),
        ("esf2", new_picks.get("e2_winner") or "TBD", new_picks.get("e3_winner") or "TBD"),
    ]
    wsf_pairs = [
        ("wsf1", new_picks.get("w1_winner") or "TBD", new_picks.get("w4_winner") or "TBD"),
        ("wsf2", new_picks.get("w2_winner") or "TBD", new_picks.get("w3_winner") or "TBD"),
    ]

    col_esf, col_wsf = st.columns(2)
    with col_esf:
        st.markdown("<div class='conf-title'>East Semis</div>", unsafe_allow_html=True)
        for sf_id, t1, t2 in esf_pairs:
            key = frozenset([t1, t2])
            live = live_series.get(key, {})
            sm = {"id": sf_id, "seed1": "?", "team1": t1, "seed2": "?", "team2": t2,
                  "leader": live.get("leader"), "score": live.get("score"),
                  "complete": live.get("complete", False)}
            w, g, s = series_pick_widget(sm, mode_key, existing, disabled or "TBD" in (t1, t2))
            new_picks[f"{sf_id}_winner"] = w
            new_picks[f"{sf_id}_games"]  = g
            if s: st.caption(f"📝 {s}")

    with col_wsf:
        st.markdown("<div class='conf-title'>West Semis</div>", unsafe_allow_html=True)
        for sf_id, t1, t2 in wsf_pairs:
            key = frozenset([t1, t2])
            live = live_series.get(key, {})
            sm = {"id": sf_id, "seed1": "?", "team1": t1, "seed2": "?", "team2": t2,
                  "leader": live.get("leader"), "score": live.get("score"),
                  "complete": live.get("complete", False)}
            w, g, s = series_pick_widget(sm, mode_key, existing, disabled or "TBD" in (t1, t2))
            new_picks[f"{sf_id}_winner"] = w
            new_picks[f"{sf_id}_games"]  = g
            if s: st.caption(f"📝 {s}")

    # ── Conference Finals ─────────────────────────────────────────────────────
    st.markdown("<div class='section-title'>Conference Finals</div>", unsafe_allow_html=True)

    ecf_t1 = new_picks.get("esf1_winner") or "TBD"
    ecf_t2 = new_picks.get("esf2_winner") or "TBD"
    wcf_t1 = new_picks.get("wsf1_winner") or "TBD"
    wcf_t2 = new_picks.get("wsf2_winner") or "TBD"

    col_ecf, col_wcf = st.columns(2)
    with col_ecf:
        st.markdown("<div class='conf-title'>East Finals</div>", unsafe_allow_html=True)
        key = frozenset([ecf_t1, ecf_t2])
        live = live_series.get(key, {})
        ecf_m = {"id": "ecf", "seed1": "?", "team1": ecf_t1, "seed2": "?", "team2": ecf_t2,
                 "leader": live.get("leader"), "score": live.get("score"),
                 "complete": live.get("complete", False)}
        w, g, s = series_pick_widget(ecf_m, mode_key, existing, disabled or "TBD" in (ecf_t1, ecf_t2))
        new_picks["ecf_winner"] = w; new_picks["ecf_games"] = g
        if s: st.caption(f"📝 {s}")

    with col_wcf:
        st.markdown("<div class='conf-title'>West Finals</div>", unsafe_allow_html=True)
        key = frozenset([wcf_t1, wcf_t2])
        live = live_series.get(key, {})
        wcf_m = {"id": "wcf", "seed1": "?", "team1": wcf_t1, "seed2": "?", "team2": wcf_t2,
                 "leader": live.get("leader"), "score": live.get("score"),
                 "complete": live.get("complete", False)}
        w, g, s = series_pick_widget(wcf_m, mode_key, existing, disabled or "TBD" in (wcf_t1, wcf_t2))
        new_picks["wcf_winner"] = w; new_picks["wcf_games"] = g
        if s: st.caption(f"📝 {s}")

    # ── NBA Finals ────────────────────────────────────────────────────────────
    st.markdown("<div class='section-title'>🏆 NBA Finals</div>", unsafe_allow_html=True)
    fin_t1 = new_picks.get("ecf_winner") or "TBD"
    fin_t2 = new_picks.get("wcf_winner") or "TBD"
    key = frozenset([fin_t1, fin_t2])
    live = live_series.get(key, {})
    fin_m = {"id": "finals", "seed1": "E", "team1": fin_t1, "seed2": "W", "team2": fin_t2,
             "leader": live.get("leader"), "score": live.get("score"),
             "complete": live.get("complete", False)}
    w, g, s = series_pick_widget(fin_m, mode_key, existing, disabled or "TBD" in (fin_t1, fin_t2))
    new_picks["finals_winner"] = w; new_picks["finals_games"] = g
    if s:
        st.success(f"🏆 Your {mode_label} champion: **{s}**")

    # ── Save ──────────────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button(f"💾  Save {mode_label} picks", key=f"save_{mode_key}",
                 disabled=is_locked, use_container_width=False):
        with st.spinner("Saving to GitHub…"):
            ap = load_all_picks()
            if ukey not in ap:
                ap[ukey] = {"display_name": username.strip()}
            ap[ukey][mode_key]    = new_picks
            ap[ukey]["updated_at"] = datetime.utcnow().isoformat()
            save_all_picks(ap)
        st.success("✅ Picks saved to GitHub!")
        st.rerun()

    return new_picks


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════

tab_my, tab_everyone = st.tabs(["📋  My Bracket", "👀  Everyone's Picks"])


# ── My Bracket ────────────────────────────────────────────────────────────────

with tab_my:
    all_picks = load_all_picks()

    col_n, col_b = st.columns([3, 1])
    with col_n:
        username = st.text_input("Your name", placeholder="Enter your name",
                                  label_visibility="collapsed", key="username")
    with col_b:
        st.button("Load picks", use_container_width=True)

    if not username.strip():
        st.info("👆 Enter your name above to get started.")
        st.stop()

    ukey      = user_key(username)
    user_data = all_picks.get(ukey, {})
    is_locked = user_data.get("locked", False)

    if is_locked:
        st.markdown('<div class="locked-banner">🔒 Your picks are locked in — no more changes. Good luck!</div>',
                    unsafe_allow_html=True)

    st.markdown("---")
    desired_tab, predicted_tab = st.tabs(["❤️  Desired Outcome", "🧠  Predicted Outcome"])

    with desired_tab:
        render_bracket_mode("desired",   "Desired",   "#e91e63",
                            user_data.get("desired",   {}), is_locked, username, ukey)

    with predicted_tab:
        render_bracket_mode("predicted", "Predicted", "#1976d2",
                            user_data.get("predicted", {}), is_locked, username, ukey)

    # ── Lock ──────────────────────────────────────────────────────────────────
    st.markdown("---")
    fresh         = load_all_picks().get(ukey, {})
    has_desired   = bool(fresh.get("desired",   {}).get("finals_winner"))
    has_predicted = bool(fresh.get("predicted", {}).get("finals_winner"))
    both_done     = has_desired and has_predicted

    lock_col, _ = st.columns([1, 2])
    with lock_col:
        if st.button("🔒  Lock ALL picks permanently",
                     disabled=is_locked or not both_done,
                     use_container_width=True,
                     help="Save both Desired and Predicted picks through the Finals first."):
            with st.spinner("Locking…"):
                ap = load_all_picks()
                if ukey not in ap:
                    ap[ukey] = {}
                ap[ukey]["locked"]    = True
                ap[ukey]["locked_at"] = datetime.utcnow().isoformat()
                save_all_picks(ap)
            st.success("🔒 Picks locked!")
            st.rerun()

    if not both_done and not is_locked:
        missing = []
        if not has_desired:   missing.append("Desired")
        if not has_predicted: missing.append("Predicted")
        st.caption(f"Save your {' and '.join(missing)} picks through the Finals before locking.")


# ── Everyone's Picks ──────────────────────────────────────────────────────────

with tab_everyone:
    all_picks = load_all_picks()

    if not all_picks:
        st.info("No picks yet — be the first!")
    else:
        st.markdown(f"**{len(all_picks)} participant{'s' if len(all_picks)!=1 else ''}** have entered picks.")

        def build_pick_row(name, locked, picks, mode_label):
            row = {
                "Name":   name,
                "Type":   mode_label,
                "Status": "🔒" if locked else "✏️",
            }
            for m in all_matchups_live:
                w = picks.get(f"{m['id']}_winner") or "—"
                g = picks.get(f"{m['id']}_games")  or ""
                cell = f"{w} ({g})" if w != "—" and g else w
                if m.get("complete") and m.get("leader") and w != "—":
                    cell = ("✅ " if w == m["leader"] else "❌ ") + cell
                short = f"{m['team1'].split()[-1]}/{m['team2'].split()[-1]}"
                row[short] = cell
            fw = picks.get("finals_winner") or "—"
            fg = picks.get("finals_games")  or ""
            row["🏆 Champion"] = f"{fw} ({fg})" if fw != "—" and fg else fw
            return row

        rows = []
        for uk, ud in all_picks.items():
            name   = ud.get("display_name", uk)
            locked = ud.get("locked", False)
            # Always emit desired row first, then predicted — blank row in between per person
            for mode_label, mode_key in [("❤️ Desired", "desired"), ("🧠 Predicted", "predicted")]:
                picks = ud.get(mode_key, {})
                rows.append(build_pick_row(name, locked, picks, mode_label))

        df = pd.DataFrame(rows)

        # Style: shade every 4 rows (2 per person × alternating persons) for readability
        def stripe_rows(styler):
            n = len(styler.data)
            styles = []
            for i in range(n):
                person_idx = i // 2   # 2 rows per person
                bg = "background-color: #f7f7f7" if person_idx % 2 == 0 else ""
                styles.append([bg] * len(styler.data.columns))
            return pd.DataFrame(styles, index=styler.data.index, columns=styler.data.columns)

        styled = df.style.apply(stripe_rows, axis=None)
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # ── Distribution ──────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### First Round Pick Distribution")
        view_dist = st.radio("Distribution for:", ["❤️ Desired", "🧠 Predicted"],
                             horizontal=True, key="dist_view")
        vk_dist = "desired" if "Desired" in view_dist else "predicted"

        for conf_label, matchups in [("Eastern Conference", east_r1), ("Western Conference", west_r1)]:
            st.markdown(f"**{conf_label}**")
            cols = st.columns(len(matchups))
            for col, m in zip(cols, matchups):
                with col:
                    t1c   = sum(1 for u in all_picks.values() if u.get(vk_dist, {}).get(f"{m['id']}_winner") == m["team1"])
                    t2c   = sum(1 for u in all_picks.values() if u.get(vk_dist, {}).get(f"{m['id']}_winner") == m["team2"])
                    total = max(t1c + t2c, 1)
                    st.markdown(f"<small><b>({m['seed1']}) {m['team1']}</b></small>", unsafe_allow_html=True)
                    st.progress(t1c / total, text=str(t1c))
                    st.markdown(f"<small><b>({m['seed2']}) {m['team2']}</b></small>", unsafe_allow_html=True)
                    st.progress(t2c / total, text=str(t2c))

