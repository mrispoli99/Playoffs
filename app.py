import streamlit as st
import json
import os
from datetime import datetime

st.set_page_config(
    page_title="2026 NBA Playoff Bracket Challenge",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Bracket Data ──────────────────────────────────────────────────────────────

EAST_R1 = [
    {"id": "e1", "seed1": 1, "team1": "Pistons",   "seed2": 8, "team2": "Magic",          "result": None,        "score": None},
    {"id": "e2", "seed1": 2, "team1": "Celtics",   "seed2": 7, "team2": "76ers",           "result": None,        "score": None},
    {"id": "e3", "seed1": 3, "team1": "Knicks",    "seed2": 6, "team2": "Hawks",           "result": "Knicks",    "score": "1-0"},
    {"id": "e4", "seed1": 4, "team1": "Cavaliers", "seed2": 5, "team2": "Raptors",         "result": "Cavaliers", "score": "1-0"},
]
WEST_R1 = [
    {"id": "w1", "seed1": 1, "team1": "Thunder",      "seed2": 8, "team2": "Suns",          "result": None,      "score": None},
    {"id": "w2", "seed1": 2, "team1": "Spurs",        "seed2": 7, "team2": "Trail Blazers", "result": None,      "score": None},
    {"id": "w3", "seed1": 3, "team1": "Nuggets",      "seed2": 6, "team2": "Timberwolves",  "result": "Nuggets", "score": "1-0"},
    {"id": "w4", "seed1": 4, "team1": "Lakers",       "seed2": 5, "team2": "Rockets",       "result": None,      "score": None},
]
ALL_MATCHUPS = EAST_R1 + WEST_R1
SERIES_LENGTHS = ["4-0", "4-1", "4-2", "4-3"]
STORAGE_FILE = "picks.json"


# ── Persistence ───────────────────────────────────────────────────────────────

def load_all_picks():
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_all_picks(data):
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def user_key(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
.main .block-container { padding-top: 1.5rem; max-width: 1120px; }

.page-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%);
    border-radius: 14px; padding: 26px 30px; margin-bottom: 20px; color: white;
}
.page-header h1 { margin:0; font-size:26px; font-weight:700; color:white; }
.page-header p  { margin:6px 0 0; font-size:13px; color:#aac; }

.matchup-box {
    border: 1px solid #e4e4e4; border-radius: 10px;
    overflow: hidden; margin-bottom: 6px; background: #fafafa;
}
.matchup-label {
    font-size: 10px; font-weight: 700; color: #bbb;
    padding: 5px 11px 3px; background: white;
    border-bottom: 1px solid #f0f0f0; text-transform: uppercase; letter-spacing: .06em;
}
.team-row {
    display: flex; align-items: center; padding: 7px 11px; gap: 7px;
    border-bottom: 1px solid #f2f2f2; font-size: 13px;
}
.team-row:last-child { border-bottom: none; }
.team-row.winner { background: #eef6ff; }
.seed { font-size:10px; font-weight:700; color:#bbb; min-width:14px; }
.live-score { font-size:10px; padding:2px 7px; border-radius:20px;
              background:#e8f5e9; color:#2e7d32; font-weight:600; }

.locked-banner { background:#fff3e0; border:1px solid #ffcc80; border-radius:8px;
                 padding:9px 14px; font-size:13px; color:#bf360c; margin-bottom:12px; }
.saved-banner  { background:#e8f5e9; border:1px solid #a5d6a7; border-radius:8px;
                 padding:9px 14px; font-size:13px; color:#1b5e20; margin-bottom:12px; }

.section-title { font-size:12px; font-weight:700; color:#555;
                 text-transform:uppercase; letter-spacing:.08em; margin:16px 0 8px; }
.conf-title    { font-size:11px; font-weight:700; color:#999;
                 text-transform:uppercase; letter-spacing:.08em; margin-bottom:8px; }
</style>
""", unsafe_allow_html=True)


# ── Page Header ───────────────────────────────────────────────────────────────

st.markdown("""
<div class="page-header">
  <h1>🏀 2026 NBA Playoff Bracket Challenge</h1>
  <p>Make two brackets — your <b>Desired Outcome ❤️</b> (who you <i>want</i> to win)
     and your <b>Predicted Outcome 🧠</b> (who you <i>think</i> will win) — including series length in games.
     Lock both in before games tip off!</p>
</div>
""", unsafe_allow_html=True)


# ── Series Pick Helper ────────────────────────────────────────────────────────

def series_pick_widget(matchup: dict, prefix: str, existing: dict, disabled: bool):
    """
    Renders matchup display + winner/games selectors.
    Returns (winner_val, games_val, summary_str).
    """
    mid  = matchup["id"]
    t1   = matchup["team1"]
    t2   = matchup["team2"]
    s1   = matchup["seed1"]
    s2   = matchup["seed2"]
    live = matchup.get("result")

    t1_cls = "team-row"
    t2_cls = "team-row"
    score_html = ""
    if live:
        t1_cls = "team-row winner" if live == t1 else "team-row"
        t2_cls = "team-row winner" if live == t2 else "team-row"
        score_html = f'<span class="live-score">{matchup["score"]}</span>'

    st.markdown(f"""
    <div class="matchup-box">
      <div class="matchup-label">({s1}) {t1} vs ({s2}) {t2} {score_html}</div>
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
        games = st.selectbox("Games", games_opts, index=g_idx,
                             key=f"{prefix}_{mid}_g", disabled=disabled,
                             label_visibility="collapsed")

    w_val = winner if winner != "— winner —" else None
    g_val = games  if games  != "— games —"  else None
    summary = f"{w_val} in {g_val}" if w_val and g_val else None
    return w_val, g_val, summary


# ── Build one full bracket for a given mode ───────────────────────────────────

def render_bracket_mode(mode_key: str, mode_label: str, mode_color: str,
                        existing: dict, is_locked: bool, username: str, ukey: str):
    disabled = is_locked
    new_picks = {}

    st.markdown(
        f"<p style='font-size:13px;color:{mode_color};margin-bottom:4px;font-weight:600;'>"
        f"{'Who you want to win each series' if mode_key=='desired' else 'Who you think will actually win each series'}"
        f" — and in how many games.</p>",
        unsafe_allow_html=True,
    )

    # ── Round 1 ───────────────────────────────────────────────────────────────
    st.markdown("<div class='section-title'>First Round</div>", unsafe_allow_html=True)
    col_e, col_w = st.columns(2)

    with col_e:
        st.markdown("<div class='conf-title'>Eastern Conference</div>", unsafe_allow_html=True)
        for m in EAST_R1:
            w, g, s = series_pick_widget(m, mode_key, existing, disabled)
            new_picks[f"{m['id']}_winner"] = w
            new_picks[f"{m['id']}_games"]  = g
            if s:
                st.caption(f"📝 {s}")

    with col_w:
        st.markdown("<div class='conf-title'>Western Conference</div>", unsafe_allow_html=True)
        for m in WEST_R1:
            w, g, s = series_pick_widget(m, mode_key, existing, disabled)
            new_picks[f"{m['id']}_winner"] = w
            new_picks[f"{m['id']}_games"]  = g
            if s:
                st.caption(f"📝 {s}")

    # ── Semis ─────────────────────────────────────────────────────────────────
    st.markdown("<div class='section-title'>Conference Semifinals</div>", unsafe_allow_html=True)

    # NBA bracket: 1v8 winner plays 4v5 winner; 2v7 winner plays 3v6 winner
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
            sm = {"id": sf_id, "seed1": "?", "team1": t1, "seed2": "?", "team2": t2,
                  "result": None, "score": None}
            locked_sf = disabled or "TBD" in (t1, t2)
            w, g, s = series_pick_widget(sm, mode_key, existing, locked_sf)
            new_picks[f"{sf_id}_winner"] = w
            new_picks[f"{sf_id}_games"]  = g
            if s: st.caption(f"📝 {s}")

    with col_wsf:
        st.markdown("<div class='conf-title'>West Semis</div>", unsafe_allow_html=True)
        for sf_id, t1, t2 in wsf_pairs:
            sm = {"id": sf_id, "seed1": "?", "team1": t1, "seed2": "?", "team2": t2,
                  "result": None, "score": None}
            locked_sf = disabled or "TBD" in (t1, t2)
            w, g, s = series_pick_widget(sm, mode_key, existing, locked_sf)
            new_picks[f"{sf_id}_winner"] = w
            new_picks[f"{sf_id}_games"]  = g
            if s: st.caption(f"📝 {s}")

    # ── Conference Finals ─────────────────────────────────────────────────────
    st.markdown("<div class='section-title'>Conference Finals</div>", unsafe_allow_html=True)
    col_ecf, col_wcf = st.columns(2)

    ecf_t1 = new_picks.get("esf1_winner") or "TBD"
    ecf_t2 = new_picks.get("esf2_winner") or "TBD"
    wcf_t1 = new_picks.get("wsf1_winner") or "TBD"
    wcf_t2 = new_picks.get("wsf2_winner") or "TBD"

    with col_ecf:
        st.markdown("<div class='conf-title'>East Finals</div>", unsafe_allow_html=True)
        ecf_m = {"id": "ecf", "seed1": "?", "team1": ecf_t1, "seed2": "?", "team2": ecf_t2,
                 "result": None, "score": None}
        w, g, s = series_pick_widget(ecf_m, mode_key, existing, disabled or "TBD" in (ecf_t1, ecf_t2))
        new_picks["ecf_winner"] = w; new_picks["ecf_games"] = g
        if s: st.caption(f"📝 {s}")

    with col_wcf:
        st.markdown("<div class='conf-title'>West Finals</div>", unsafe_allow_html=True)
        wcf_m = {"id": "wcf", "seed1": "?", "team1": wcf_t1, "seed2": "?", "team2": wcf_t2,
                 "result": None, "score": None}
        w, g, s = series_pick_widget(wcf_m, mode_key, existing, disabled or "TBD" in (wcf_t1, wcf_t2))
        new_picks["wcf_winner"] = w; new_picks["wcf_games"] = g
        if s: st.caption(f"📝 {s}")

    # ── NBA Finals ────────────────────────────────────────────────────────────
    st.markdown("<div class='section-title'>🏆 NBA Finals</div>", unsafe_allow_html=True)
    fin_t1 = new_picks.get("ecf_winner") or "TBD"
    fin_t2 = new_picks.get("wcf_winner") or "TBD"
    fin_m  = {"id": "finals", "seed1": "E", "team1": fin_t1, "seed2": "W", "team2": fin_t2,
              "result": None, "score": None}
    w, g, s = series_pick_widget(fin_m, mode_key, existing, disabled or "TBD" in (fin_t1, fin_t2))
    new_picks["finals_winner"] = w; new_picks["finals_games"] = g
    if s:
        st.success(f"🏆 Your {mode_label} champion: **{s}**")

    # ── Save ──────────────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button(f"💾  Save {mode_label} picks", key=f"save_{mode_key}",
                 disabled=is_locked, use_container_width=False):
        ap = load_all_picks()
        if ukey not in ap:
            ap[ukey] = {"display_name": username.strip()}
        ap[ukey][mode_key] = new_picks
        ap[ukey]["updated_at"] = datetime.utcnow().isoformat()
        save_all_picks(ap)
        st.success("✅ Picks saved!")
        st.rerun()

    return new_picks


# ═════════════════════════════════════════════════════════════════════════════
# TABS
# ═════════════════════════════════════════════════════════════════════════════

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

    ukey = user_key(username)
    user_data = all_picks.get(ukey, {})
    is_locked = user_data.get("locked", False)

    if is_locked:
        st.markdown('<div class="locked-banner">🔒 Your picks are locked in — no more changes. Good luck!</div>',
                    unsafe_allow_html=True)

    st.markdown("---")
    desired_tab, predicted_tab = st.tabs(["❤️  Desired Outcome", "🧠  Predicted Outcome"])

    with desired_tab:
        d_picks = render_bracket_mode(
            "desired", "Desired", "#e91e63",
            user_data.get("desired", {}), is_locked, username, ukey,
        )

    with predicted_tab:
        p_picks = render_bracket_mode(
            "predicted", "Predicted", "#1976d2",
            user_data.get("predicted", {}), is_locked, username, ukey,
        )

    # ── Lock button ───────────────────────────────────────────────────────────
    st.markdown("---")
    fresh = load_all_picks().get(ukey, {})
    has_desired   = bool(fresh.get("desired",   {}).get("finals_winner"))
    has_predicted = bool(fresh.get("predicted", {}).get("finals_winner"))
    both_done = has_desired and has_predicted

    lock_col, _ = st.columns([1, 2])
    with lock_col:
        if st.button("🔒  Lock ALL picks permanently", disabled=is_locked or not both_done,
                     use_container_width=True,
                     help="You must save both Desired and Predicted picks (through the Finals) before locking."):
            ap = load_all_picks()
            if ukey not in ap:
                ap[ukey] = {}
            ap[ukey]["locked"] = True
            ap[ukey]["locked_at"] = datetime.utcnow().isoformat()
            save_all_picks(ap)
            st.success("🔒 Picks locked! No further changes allowed.")
            st.rerun()

    if not both_done and not is_locked:
        missing = []
        if not has_desired:   missing.append("Desired")
        if not has_predicted: missing.append("Predicted")
        st.caption(f"Save your {' and '.join(missing)} picks through the Finals before locking.")


# ── Everyone's Picks ──────────────────────────────────────────────────────────

with tab_everyone:
    import pandas as pd
    all_picks = load_all_picks()

    if not all_picks:
        st.info("No picks yet — be the first!")
    else:
        st.markdown(f"**{len(all_picks)} participant{'s' if len(all_picks)!=1 else ''}** have entered picks.")

        view = st.radio("Show picks:", ["❤️ Desired Outcome", "🧠 Predicted Outcome"],
                        horizontal=True, key="ev_view")
        vk = "desired" if "Desired" in view else "predicted"

        rows = []
        for uk, ud in all_picks.items():
            name   = ud.get("display_name", uk)
            locked = ud.get("locked", False)
            picks  = ud.get(vk, {})

            row = {"Name": name, "Status": "🔒 Locked" if locked else "✏️ Open"}
            for m in ALL_MATCHUPS:
                w = picks.get(f"{m['id']}_winner") or "—"
                g = picks.get(f"{m['id']}_games")  or ""
                cell = f"{w} ({g})" if w != "—" and g else w
                if m["result"] and w != "—":
                    cell = ("✅ " if w == m["result"] else "❌ ") + cell
                short = f"{m['team1'].split()[-1]}/{m['team2'].split()[-1]}"
                row[short] = cell

            fw = picks.get("finals_winner") or "—"
            fg = picks.get("finals_games")  or ""
            row["🏆 Champion"] = f"{fw} ({fg})" if fw != "—" and fg else fw
            rows.append(row)

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # ── Distribution charts ───────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### First Round Pick Distribution")
        for conf_label, matchups in [("Eastern Conference", EAST_R1), ("Western Conference", WEST_R1)]:
            st.markdown(f"**{conf_label}**")
            cols = st.columns(len(matchups))
            for col, m in zip(cols, matchups):
                with col:
                    t1c = sum(1 for u in all_picks.values() if u.get(vk,{}).get(f"{m['id']}_winner")==m["team1"])
                    t2c = sum(1 for u in all_picks.values() if u.get(vk,{}).get(f"{m['id']}_winner")==m["team2"])
                    total = max(t1c + t2c, 1)
                    st.markdown(f"<small><b>({m['seed1']}) {m['team1']}</b></small>", unsafe_allow_html=True)
                    st.progress(t1c / total, text=f"{t1c}")
                    st.markdown(f"<small><b>({m['seed2']}) {m['team2']}</b></small>", unsafe_allow_html=True)
                    st.progress(t2c / total, text=f"{t2c}")
