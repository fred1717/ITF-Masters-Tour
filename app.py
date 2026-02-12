#!/usr/bin/env python3

from datetime import datetime, date, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

from src.modules.db_connection import DatabaseConnection
from src.modules.ranking_window import (
    entry_deadline_dt_for_tournament_week,
    draw_publication_dt_for_tournament_week,
)

from src.modules.rules_engine import AgeCategoryRule, required_age_category_id
from scripts.services.entry_service import EntryRequest, create_entry
from scripts.services.draw_service import DrawGenerationRequest, generate_draw_from_entries
from scripts.services.match_service import create_match_skeleton, ResultPayload, apply_result_and_advance
from scripts.services.view_service import get_draw_matches


app = Flask(__name__)
app.secret_key = "dev-only-change-me"


# Add a root route that redirects to /tournaments
@app.get("/")
def home():
    return redirect(url_for("tournaments"))


# Stop favicon 404 noise
@app.get("/tournaments")
def tournaments():
    db = DatabaseConnection()
    if not db.connect():
        return "DB connection failed", 500

    rows = db.query("""
        SELECT tournament_id, name, start_date, end_date, tournament_year, tournament_week
        FROM Tournaments
        ORDER BY tournament_year DESC, tournament_week DESC, tournament_id DESC
        LIMIT 200
    """)
    db.disconnect()
    return render_template("tournaments.html", tournaments=rows)


@app.get("/draw/<int:draw_id>")
def draw_view(draw_id: int):
    matches = get_draw_matches(draw_id)
    return render_template("draw.html", draw_id=draw_id, matches=matches)


@app.get("/admin")
def admin_home():
    return render_template("admin.html")


@app.get("/api/draw-info/<int:draw_id>")
def api_draw_info(draw_id):
    db = DatabaseConnection()
    if not db.connect():
        return {"error": "DB failed"}, 500
    row = db.query_params(
        "SELECT has_supertiebreak FROM Draws WHERE draw_id = %s",
        (draw_id,),
    )
    db.disconnect()
    if not row:
        return {"error": "Not found"}, 404
    return {"has_supertiebreak": bool(row[0]["has_supertiebreak"])}


@app.post("/admin/entry")
def admin_create_entry():
    try:
        req = EntryRequest(
            tournament_id=int(request.form["tournament_id"]),
            player_id=int(request.form["player_id"]),
            age_category_id=int(request.form["age_category_id"]),
            gender_id=int(request.form["gender_id"]),
            entry_points=int(request.form.get("entry_points", "0")),
            entry_timestamp=datetime.now(tz=timezone.utc),
        )
        result = create_entry(req)
        flash(f"✓ Entry created: player {result['player_id']} → tournament {result['tournament_id']}")
    except Exception as e:
        flash(f"✗ Entry failed: {e}")
    return redirect(url_for("admin_home"))


@app.post("/admin/generate-draw")
def admin_generate_draw():
    try:
        has_stb = request.form.get("has_supertiebreak", "true").lower() in ("true", "1", "yes", "on")
        req = DrawGenerationRequest(
            tournament_id=int(request.form["tournament_id"]),
            age_category_id=int(request.form["age_category_id"]),
            gender_id=int(request.form["gender_id"]),
            draw_status_id=3,
            has_supertiebreak=(request.form.get("has_supertiebreak", "true").lower() == "true"),
            draw_generated_at=datetime.now(tz=timezone.utc),
        )
        result = generate_draw_from_entries(req)
        flash(f"✓ Draw generated: draw_id={result['draw_id']}, {result['draw_players_created']} players placed")
        return redirect(url_for("draw_view", draw_id=result["draw_id"]))
    except Exception as e:
        flash(f"✗ Draw generation failed: {e}")
        return redirect(url_for("admin_home"))


@app.post("/admin/create-skeleton")
def admin_create_skeleton():
    draw_id = int(request.form["draw_id"])
    try:
        tournament_start = request.form.get("tournament_start_date")
        tsd = datetime.strptime(tournament_start, "%Y-%m-%d").date() if tournament_start else date.today()
        result = create_match_skeleton(draw_id=draw_id, tournament_start_date=tsd)
        flash(f"✓ Match skeleton created: {result['matches_created']} matches for draw {draw_id}")
        return redirect(url_for("draw_view", draw_id=draw_id))
    except Exception as e:
        flash(f"✗ Skeleton creation failed: {e}")
        return redirect(url_for("admin_home"))


@app.post("/admin/submit-result")
def admin_submit_result():
    draw_id = int(request.form["draw_id"])
    try:
        payload = ResultPayload(
            match_id=int(request.form["match_id"]),
            match_status_id=int(request.form["match_status_id"]),
            winner_id=int(request.form["winner_id"]),

            set1_player1=int(request.form["set1_p1"]) if request.form.get("set1_p1") else None,
            set1_player2=int(request.form["set1_p2"]) if request.form.get("set1_p2") else None,
            set1_tiebreak_player1=int(request.form["set1_tb_p1"]) if request.form.get("set1_tb_p1") else None,
            set1_tiebreak_player2=int(request.form["set1_tb_p2"]) if request.form.get("set1_tb_p2") else None,

            set2_player1=int(request.form["set2_p1"]) if request.form.get("set2_p1") else None,
            set2_player2=int(request.form["set2_p2"]) if request.form.get("set2_p2") else None,
            set2_tiebreak_player1=int(request.form["set2_tb_p1"]) if request.form.get("set2_tb_p1") else None,
            set2_tiebreak_player2=int(request.form["set2_tb_p2"]) if request.form.get("set2_tb_p2") else None,

            set3_player1=int(request.form["set3_p1"]) if request.form.get("set3_p1") else None,
            set3_player2=int(request.form["set3_p2"]) if request.form.get("set3_p2") else None,
            set3_tiebreak_player1=int(request.form["set3_tb_p1"]) if request.form.get("set3_tb_p1") else None,
            set3_tiebreak_player2=int(request.form["set3_tb_p2"]) if request.form.get("set3_tb_p2") else None,

            set3_supertiebreak_player1=int(request.form["stb_p1"]) if request.form.get("stb_p1") else None,
            set3_supertiebreak_player2=int(request.form["stb_p2"]) if request.form.get("stb_p2") else None,
        )

        res = apply_result_and_advance(draw_id=draw_id, payload=payload)
        flash("✓ Result saved" + (" and winner advanced" if res.get("advanced_to_round_id") else ""))
        return redirect(url_for("draw_view", draw_id=draw_id))
    except Exception as e:
        flash(f"✗ Result submission failed: {e}")
        return redirect(url_for("admin_home"))


# ---------------------------------------------------------------------------
# PAGE ROUTES
# ---------------------------------------------------------------------------

@app.get("/tournament/<int:tournament_id>")
def tournament_detail(tournament_id: int):
    db = DatabaseConnection()
    if not db.connect():
        return "DB connection failed", 500

    tournament = db.query_params(
        """
        SELECT t.tournament_id, t.name, t.start_date, t.end_date,
               t.tournament_year, t.tournament_week,
               tc.description AS category, s.surface_name,
               v.venue_name, l.city, c.description AS country
        FROM Tournaments t
        LEFT JOIN TournamentCategory tc ON tc.category_id = t.category_id
        LEFT JOIN Surfaces s ON s.surface_id = t.surface_id
        LEFT JOIN Venue v ON v.venue_id = t.venue_id
        LEFT JOIN Location l ON l.location_id = v.location_id
        LEFT JOIN Country c ON c.country_id = l.country_id
        WHERE t.tournament_id = %s
        """,
        (tournament_id,),
    )
    if not tournament:
        db.disconnect()
        return "Tournament not found", 404

    draws = db.query_params(
        """
        SELECT d.draw_id, d.age_category_id, d.gender_id, d.draw_status_id,
               d.num_players, d.has_supertiebreak, d.draw_generated_at,
               ac.code AS age_code, g.code AS gender_code,
               ds.status_name AS draw_status
        FROM Draws d
        LEFT JOIN AgeCategory ac ON ac.age_category_id = d.age_category_id
        LEFT JOIN Gender g ON g.gender_id = d.gender_id
        LEFT JOIN DrawStatus ds ON ds.status_id = d.draw_status_id
        WHERE d.tournament_id = %s
        ORDER BY d.gender_id, d.age_category_id
        """,
        (tournament_id,),
    )

    entries = db.query_params(
        """
        SELECT e.entry_id, e.player_id, e.age_category_id, e.gender_id,
               e.entry_points, e.entry_timestamp,
               p.first_name, p.last_name,
               ac.code AS age_code, g.code AS gender_code
        FROM Entries e
        JOIN Players p ON p.player_id = e.player_id
        LEFT JOIN AgeCategory ac ON ac.age_category_id = e.age_category_id
        LEFT JOIN Gender g ON g.gender_id = e.gender_id
        WHERE e.tournament_id = %s
        ORDER BY e.gender_id, e.age_category_id, e.entry_points DESC
        """,
        (tournament_id,),
    )
    db.disconnect()

    return render_template(
        "tournament_detail.html",
        tournament=tournament[0],
        draws=draws,
        entries=entries,
    )


@app.get("/rankings")
def rankings():
    db = DatabaseConnection()
    if not db.connect():
        return "DB connection failed", 500

    # Default: latest available week
    req_year = request.args.get("year", type=int)
    req_week = request.args.get("week", type=int)

    if req_year and req_week:
        ry, rw = req_year, req_week
    else:
        latest = db.query(
            """
            SELECT ranking_year, ranking_week
            FROM WeeklyRanking
            ORDER BY ranking_year DESC, ranking_week DESC
            LIMIT 1
            """
        )
        if not latest:
            db.disconnect()
            return render_template("rankings.html", rankings=[], year=None, week=None)
        ry = latest[0]["ranking_year"]
        rw = latest[0]["ranking_week"]

    rows = db.query_params(
        """
        SELECT wr.rank_position, wr.total_points, wr.player_id,
               wr.age_category_id, wr.gender_id,
               p.first_name, p.last_name, c.description AS country,
               ac.code AS age_code, g.code AS gender_code
        FROM WeeklyRanking wr
        JOIN Players p ON p.player_id = wr.player_id
        LEFT JOIN Country c ON c.country_id = p.country_id
        LEFT JOIN AgeCategory ac ON ac.age_category_id = wr.age_category_id
        LEFT JOIN Gender g ON g.gender_id = wr.gender_id
        WHERE wr.ranking_year = %s AND wr.ranking_week = %s
        ORDER BY wr.age_category_id, wr.gender_id, wr.rank_position
        """,
        (ry, rw),
    )
    db.disconnect()

    return render_template("rankings.html", rankings=rows, year=ry, week=rw)


# ---------------------------------------------------------------------------
# JSON API ROUTES (for admin form dropdowns and AJAX)
# ---------------------------------------------------------------------------

@app.get("/api/players/search")
def api_player_search():
    """Search players by name fragment. Used by admin entry form autocomplete."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])

    db = DatabaseConnection()
    if not db.connect():
        return jsonify({"error": "DB connection failed"}), 500

    rows = db.query_params(
        """
        SELECT p.player_id, p.first_name, p.last_name, p.birth_year,
               p.gender_id, g.code AS gender_code,
               c.description AS country
        FROM Players p
        LEFT JOIN Gender g ON g.gender_id = p.gender_id
        LEFT JOIN Country c ON c.country_id = p.country_id
        WHERE p.status_id = 1
          AND (LOWER(p.first_name) LIKE LOWER(%s) OR LOWER(p.last_name) LIKE LOWER(%s))
        ORDER BY p.last_name, p.first_name
        LIMIT 30
        """,
        (f"%{q}%", f"%{q}%"),
    )
    db.disconnect()

    return jsonify([
        {
            "player_id": r["player_id"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "birth_year": r["birth_year"],
            "gender_id": r["gender_id"],
            "gender_code": r["gender_code"],
            "country": r["country"],
        }
        for r in rows
    ])


@app.get("/api/reference-data")
def api_reference_data():
    """Age categories, genders, match statuses for admin dropdowns."""
    db = DatabaseConnection()
    if not db.connect():
        return jsonify({"error": "DB connection failed"}), 500

    age_cats = db.query("SELECT age_category_id, code, description, min_age, max_age FROM AgeCategory ORDER BY age_category_id")
    genders = db.query("SELECT gender_id, code, description FROM Gender ORDER BY gender_id")
    match_statuses = db.query("SELECT match_status_id, code, description FROM MatchStatus ORDER BY match_status_id")
    db.disconnect()

    return jsonify({
        "age_categories": age_cats,
        "genders": genders,
        "match_statuses": match_statuses,
    })


@app.get("/api/tournaments")
def api_tournaments():
    """All tournaments for admin dropdowns. Optional ?recent=N to limit."""
    db = DatabaseConnection()
    if not db.connect():
        return jsonify({"error": "DB connection failed"}), 500

    limit = request.args.get("recent", default=20, type=int)
    rows = db.query_params(
        """
        SELECT t.tournament_id, t.name, t.start_date, t.end_date,
               t.tournament_year, t.tournament_week,
               tc.description AS category
        FROM Tournaments t
        LEFT JOIN TournamentCategory tc ON tc.category_id = t.category_id
        ORDER BY t.tournament_year DESC, t.tournament_week DESC
        LIMIT %s
        """,
        (limit,),
    )
    db.disconnect()

    result = []
    for r in rows:
        result.append({
            "tournament_id": r["tournament_id"],
            "name": r["name"],
            "start_date": str(r["start_date"]),
            "end_date": str(r["end_date"]),
            "tournament_year": r["tournament_year"],
            "tournament_week": r["tournament_week"],
            "category": r["category"],
        })
    return jsonify(result)


@app.get("/api/draw/<int:draw_id>/matches")
def api_draw_matches(draw_id: int):
    """Matches for a draw — used by admin result form to show player names."""
    db = DatabaseConnection()
    if not db.connect():
        return jsonify({"error": "DB connection failed"}), 500

    rows = db.query_params(
        """
        SELECT m.match_id, m.round_id, m.match_number,
               m.player1_id, m.player2_id, m.winner_id,
               m.match_status_id,
               mr.code AS round_code,
               p1.first_name AS p1_first, p1.last_name AS p1_last,
               p2.first_name AS p2_first, p2.last_name AS p2_last
        FROM Matches m
        JOIN MatchRounds mr ON mr.round_id = m.round_id
        LEFT JOIN Players p1 ON p1.player_id = m.player1_id
        LEFT JOIN Players p2 ON p2.player_id = m.player2_id
        WHERE m.draw_id = %s
        ORDER BY m.round_id, m.match_number
        """,
        (draw_id,),
    )
    db.disconnect()

    return jsonify([
        {
            "match_id": r["match_id"],
            "round_code": r["round_code"],
            "match_number": r["match_number"],
            "player1_id": r["player1_id"],
            "player2_id": r["player2_id"],
            "p1_name": (
                ((r["p1_first"] or "") + " " + (r["p1_last"] or "")).strip()
                or None
            ),
            "p2_name": (
                ((r["p2_first"] or "") + " " + (r["p2_last"] or "")).strip()
                or None
            ),
            "winner_id": r["winner_id"],
            "match_status_id": r["match_status_id"],
        }
        for r in rows
    ])


@app.get("/api/tournament/<int:tournament_id>/info")
def api_tournament_info(tournament_id: int):
    """Tournament metadata including computed deadlines."""
    db = DatabaseConnection()
    if not db.connect():
        return jsonify({"error": "DB connection failed"}), 500

    rows = db.query_params(
        """
        SELECT t.tournament_id, t.name, t.start_date, t.end_date,
               t.tournament_year, t.tournament_week,
               tc.description AS category
        FROM Tournaments t
        LEFT JOIN TournamentCategory tc ON tc.category_id = t.category_id
        WHERE t.tournament_id = %s
        """,
        (tournament_id,),
    )
    db.disconnect()

    if not rows:
        return jsonify({"error": "Tournament not found"}), 404

    t = rows[0]
    ty = int(t["tournament_year"])
    tw = int(t["tournament_week"])
    entry_deadline = entry_deadline_dt_for_tournament_week(ty, tw)
    draw_deadline = draw_publication_dt_for_tournament_week(ty, tw)

    return jsonify({
        "tournament_id": t["tournament_id"],
        "name": t["name"],
        "start_date": str(t["start_date"]),
        "end_date": str(t["end_date"]),
        "tournament_year": ty,
        "tournament_week": tw,
        "category": t["category"],
        "entry_deadline": entry_deadline.isoformat(),
        "draw_deadline": draw_deadline.isoformat(),
    })


@app.get("/api/tournament/<int:tournament_id>/entries")
def api_tournament_entries(tournament_id: int):
    """Entries for a tournament, optionally filtered by age_category_id and gender_id."""
    db = DatabaseConnection()
    if not db.connect():
        return jsonify({"error": "DB connection failed"}), 500

    age_cat = request.args.get("age_category_id", type=int)
    gender = request.args.get("gender_id", type=int)

    sql = """
        SELECT e.entry_id, e.player_id, e.age_category_id, e.gender_id,
               e.entry_points, e.entry_timestamp,
               p.first_name, p.last_name
        FROM Entries e
        JOIN Players p ON p.player_id = e.player_id
        WHERE e.tournament_id = %s
    """
    params = [tournament_id]

    if age_cat is not None:
        sql += " AND e.age_category_id = %s"
        params.append(age_cat)
    if gender is not None:
        sql += " AND e.gender_id = %s"
        params.append(gender)

    sql += " ORDER BY e.entry_points DESC, e.entry_timestamp ASC"

    rows = db.query_params(sql, tuple(params))
    db.disconnect()

    return jsonify([
        {
            "entry_id": r["entry_id"],
            "player_id": r["player_id"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "age_category_id": r["age_category_id"],
            "gender_id": r["gender_id"],
            "entry_points": r["entry_points"],
            "entry_timestamp": r["entry_timestamp"].isoformat() if r["entry_timestamp"] else None,
        }
        for r in rows
    ])


@app.get("/api/tournament/<int:tournament_id>/draws")
def api_tournament_draws(tournament_id: int):
    """Draws for a tournament."""
    db = DatabaseConnection()
    if not db.connect():
        return jsonify({"error": "DB connection failed"}), 500

    rows = db.query_params(
        """
        SELECT d.draw_id, d.age_category_id, d.gender_id, d.draw_status_id,
               d.num_players, d.has_supertiebreak,
               ac.code AS age_code, g.code AS gender_code,
               ds.status_name AS draw_status
        FROM Draws d
        LEFT JOIN AgeCategory ac ON ac.age_category_id = d.age_category_id
        LEFT JOIN Gender g ON g.gender_id = d.gender_id
        LEFT JOIN DrawStatus ds ON ds.status_id = d.draw_status_id
        WHERE d.tournament_id = %s
        ORDER BY d.age_category_id, d.gender_id
        """,
        (tournament_id,),
    )
    db.disconnect()

    return jsonify([dict(r) for r in rows])


@app.get("/api/player/<int:player_id>/ranking")
def api_player_ranking(player_id: int):
    """Ranking for a player at the week relevant for a tournament's seeding."""
    db = DatabaseConnection()
    if not db.connect():
        return jsonify({"error": "DB connection failed"}), 500

    tournament_id = request.args.get("tournament_id", type=int)
    tournament_year = None
    r_year, r_week = None, None
    req_ac_id = None

    if tournament_id:
        tmeta = db.query_params(
            "SELECT tournament_year, tournament_week FROM Tournaments "
            "WHERE tournament_id = %s",
            (tournament_id,),
        )
        if tmeta:
            tournament_year = int(tmeta[0]["tournament_year"])
            r_year = tournament_year
            r_week = int(tmeta[0]["tournament_week"]) - 1

    # Compute required age category FIRST
    if tournament_year:
        player_rows = db.query_params(
            "SELECT birth_year FROM Players WHERE player_id = %s",
            (player_id,),
        )
        ac_rows = db.query(
            "SELECT age_category_id, min_age, max_age "
            "FROM AgeCategory ORDER BY min_age ASC"
        )
        if player_rows and ac_rows:
            categories = tuple(
                AgeCategoryRule(
                    age_category_id=int(r["age_category_id"]),
                    min_age=int(r["min_age"]),
                    max_age=int(r["max_age"]),
                )
                for r in ac_rows
            )
            try:
                req_ac_id = required_age_category_id(
                    birth_year=int(player_rows[0]["birth_year"]),
                    tournament_year=tournament_year,
                    categories=categories,
                )
            except Exception:
                pass

    # Query ranking filtered by correct age category
    if r_year and r_week and req_ac_id:
        rows = db.query_params(
            """
            SELECT wr.total_points, wr.rank_position,
                   wr.age_category_id, wr.ranking_year, wr.ranking_week
            FROM WeeklyRanking wr
            WHERE wr.player_id = %s
              AND wr.ranking_year = %s AND wr.ranking_week = %s
              AND wr.age_category_id = %s
            LIMIT 1
            """,
            (player_id, r_year, r_week, req_ac_id),
        )
    elif r_year and r_week:
        rows = db.query_params(
            """
            SELECT wr.total_points, wr.rank_position,
                   wr.age_category_id, wr.ranking_year, wr.ranking_week
            FROM WeeklyRanking wr
            WHERE wr.player_id = %s
              AND wr.ranking_year = %s AND wr.ranking_week = %s
            ORDER BY wr.total_points DESC
            LIMIT 1
            """,
            (player_id, r_year, r_week),
        )
    else:
        rows = db.query_params(
            """
            SELECT wr.total_points, wr.rank_position,
                   wr.age_category_id, wr.ranking_year, wr.ranking_week
            FROM WeeklyRanking wr
            WHERE wr.player_id = %s
            ORDER BY wr.ranking_year DESC, wr.ranking_week DESC
            LIMIT 1
            """,
            (player_id,),
        )

    result = {"total_points": 0, "rank_position": None, "age_category_id": req_ac_id}

    if rows:
        r = rows[0]
        result["total_points"] = r["total_points"]
        result["rank_position"] = r["rank_position"]
        result["age_category_id"] = req_ac_id or r["age_category_id"]
        result["ranking_year"] = r["ranking_year"]
        result["ranking_week"] = r["ranking_week"]

    db.disconnect()
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
