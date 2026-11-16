"""Dating-app research prototype: AI-generated image label vs. no label.

End-to-end flow: consent/eligibility -> server-side block randomization ->
six profiles in individual random order (label shown only in condition 1) ->
six 1-7 ratings + like/skip per profile -> label recall, open answer,
minimal demographics -> debrief. All data are keyed by a random study code."""
import json
import secrets
import time

from flask import Flask, abort, g, make_response, redirect, render_template, request, url_for

import config
import db
import randomization


def create_app(db_path=None, seed=None, min_seconds=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or config.DB_PATH
    app.config["SEED"] = config.RANDOM_SEED if seed is None else seed
    app.config["MIN_SECONDS"] = config.MIN_SECONDS_PER_PROFILE if min_seconds is None else min_seconds

    with db.connect(app.config["DB_PATH"]) as con:
        db.init_db(con)
        randomization.ensure_allocation(con, seed=app.config["SEED"])
        load_profiles(con)

    def get_db():
        if "con" not in g:
            g.con = db.connect(app.config["DB_PATH"])
        return g.con

    @app.teardown_appcontext
    def close_db(_exc):
        con = g.pop("con", None)
        if con is not None:
            con.close()

    def participant_or_404(code):
        p = get_db().execute("SELECT * FROM participants WHERE study_code=?", (code,)).fetchone()
        if p is None:
            abort(404)
        return p

    # ---------- 1. Information, consent and eligibility ----------
    @app.get("/")
    def start():
        is_test = request.args.get("test") == "1"
        if not is_test and request.cookies.get("aitu_done"):
            return render_template("exit.html", reason="already")      # v4: one participation per browser
        return render_template("consent.html", is_test=is_test, src=(request.args.get("src") or "link")[:20])

    @app.post("/consent")
    def consent():
        f = request.form
        consented = f.get("consent") == "yes"
        eligible = all(f.get(k) == "yes" for k in ("is_student", "age_18_25", "dating_app"))
        if not consented:
            return render_template("exit.html", reason="no_consent")
        if not eligible:
            # Data minimisation: nothing is stored for ineligible visitors.
            return render_template("exit.html", reason="not_eligible")
        gender = f.get("gender")
        if gender not in config.GENDER_STRATA:
            return render_template("consent.html", is_test=f.get("is_test") == "1", src=f.get("src", "link"),
                                   error=True)
        con = get_db()
        code = "P-" + secrets.token_hex(3).upper()
        is_test = 1 if f.get("is_test") == "1" else 0
        device = request.cookies.get("aitu_dt") or secrets.token_hex(8)
        slot, cond = randomization.assign_next(con, code, is_test, stratum=gender)   # v4: gender-stratified
        ids = [r[0] for r in con.execute("SELECT profile_id FROM profiles")]
        order = randomization.profile_order(ids, code, app.config["SEED"])
        con.execute("INSERT INTO participants(study_code, condition, alloc_slot, is_test, profile_order, wave, gender, "
                    "source, device_token) VALUES (?,?,?,?,?,?,?,?,?)",
                    (code, cond, slot, is_test, ",".join(order), config.WAVE, gender,
                     (f.get("src") or "link")[:20], device))
        con.execute("INSERT INTO consent_records(study_code, consented, is_student, age_18_25, dating_app) "
                    "VALUES (?,1,1,1,1)", (code,))
        con.commit()
        resp = make_response(redirect(url_for("instructions", code=code)))
        resp.set_cookie("aitu_dt", device, max_age=60 * 60 * 24 * 365, samesite="Lax")
        return resp

    @app.get("/s/<code>/intro")
    def instructions(code):
        participant_or_404(code)
        return render_template("intro.html", code=code)

    # ---------- 2. Profile view + ratings ----------
    @app.get("/s/<code>/profile/<int:pos>")
    def profile(code, pos):
        p = participant_or_404(code)
        order = p["profile_order"].split(",")
        if not 1 <= pos <= len(order):
            abort(404)
        con = get_db()
        prof = con.execute("SELECT * FROM profiles WHERE profile_id=?", (order[pos - 1],)).fetchone()
        con.execute("INSERT OR IGNORE INTO profile_views(study_code, position, served_at) VALUES (?,?,?)",
                    (code, pos, time.time()))
        con.commit()
        return render_template("profile.html", code=code, pos=pos, total=len(order), prof=prof,
                               show_label=(p["condition"] == 1), label_text=config.LABEL_TEXT,
                               items=config.ITEMS, error=request.args.get("error"),
                               min_seconds=app.config["MIN_SECONDS"],
                               attention=(pos == config.ATTENTION_POSITION), attention_text=config.ATTENTION_TEXT)

    @app.post("/s/<code>/profile/<int:pos>")
    def submit_profile(code, pos):
        p = participant_or_404(code)
        order = p["profile_order"].split(",")
        if not 1 <= pos <= len(order):
            abort(404)
        pid = order[pos - 1]
        con = get_db()
        served = con.execute("SELECT served_at FROM profile_views WHERE study_code=? AND position=?",
                             (code, pos)).fetchone()
        if served is None or time.time() - served[0] < app.config["MIN_SECONDS"]:
            return redirect(url_for("profile", code=code, pos=pos, error="too_fast"))   # v4: server-side minimum time
        attn = None
        if pos == config.ATTENTION_POSITION:
            raw = request.form.get("attn", "")
            if not raw.isdigit() or not 1 <= int(raw) <= 7:
                return redirect(url_for("profile", code=code, pos=pos, error="incomplete"))
            attn = int(raw)
        decision = request.form.get("decision")
        values = {}
        for item_no, construct, _ in config.ITEMS:
            raw = request.form.get(f"item{item_no}", "")
            if not raw.isdigit() or not config.SCALE_MIN <= int(raw) <= config.SCALE_MAX:
                return redirect(url_for("profile", code=code, pos=pos, error="incomplete"))
            values[item_no] = (construct, int(raw))
        if decision not in ("like", "skip"):
            return redirect(url_for("profile", code=code, pos=pos, error="incomplete"))
        if attn is not None:
            con.execute("UPDATE participants SET attention_value=? WHERE study_code=?", (attn, code))
        con.executemany(
            "INSERT OR REPLACE INTO ratings(study_code, profile_id, position, item_no, construct, value, decision) "
            "VALUES (?,?,?,?,?,?,?)",
            [(code, pid, pos, n, c, v, decision) for n, (c, v) in values.items()])
        if pos == len(order):
            con.execute("UPDATE participants SET status='rated' WHERE study_code=?", (code,))
        con.commit()
        if pos < len(order):
            return redirect(url_for("profile", code=code, pos=pos + 1))
        return redirect(url_for("post", code=code))

    # ---------- 3. Client events (viewing time, like/skip, label interaction) ----------
    @app.post("/api/events")
    def events():
        data = request.get_json(silent=True) or {}
        code = data.get("study_code")
        allowed = {"view_start", "view_end", "like", "skip", "label_hover", "label_click"}
        evs = [e for e in data.get("events", []) if e.get("type") in allowed]
        con = get_db()
        if con.execute("SELECT 1 FROM participants WHERE study_code=?", (code,)).fetchone() is None:
            return {"ok": False}, 400
        con.executemany(
            "INSERT INTO events(study_code, profile_id, event_type, value_ms, client_ts) VALUES (?,?,?,?,?)",
            [(code, e.get("profile_id"), e["type"], e.get("value_ms"), e.get("ts")) for e in evs])
        con.commit()
        return {"ok": True, "stored": len(evs)}

    # ---------- 4. Recall check, open answer, demographics, debrief ----------
    @app.get("/s/<code>/post")
    def post(code):
        participant_or_404(code)
        return render_template("post.html", code=code, options=config.LABEL_TEXT_OPTIONS)

    @app.post("/s/<code>/post")
    def submit_post(code):
        participant_or_404(code)
        f = request.form
        if f.get("label_recall") not in ("yes", "no", "not_sure") or \
                f.get("label_text") not in [k for k, _ in config.LABEL_TEXT_OPTIONS]:
            return render_template("post.html", code=code, error=True, options=config.LABEL_TEXT_OPTIONS)
        con = get_db()
        g_ = con.execute("SELECT gender FROM participants WHERE study_code=?", (code,)).fetchone()[0]
        con.execute("INSERT OR REPLACE INTO post_survey(study_code, label_recall, label_text, open_text, gender, "
                    "study_year, app_use_freq) VALUES (?,?,?,?,?,?,?)",
                    (code, f["label_recall"], f["label_text"], (f.get("open_text") or "").strip()[:1000] or None,
                     {"F": "Female", "M": "Male"}.get(g_), f.get("study_year") or None, f.get("app_use_freq") or None))
        con.execute("UPDATE participants SET status='completed', "
                    "completed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE study_code=?", (code,))
        con.commit()
        return redirect(url_for("debrief", code=code))

    @app.get("/s/<code>/debrief")
    def debrief(code):
        p = participant_or_404(code)
        resp = make_response(render_template("debrief.html", code=code))
        if not p["is_test"]:
            resp.set_cookie("aitu_done", "1", max_age=60 * 60 * 24 * 365, samesite="Lax")
        return resp

    return app


def load_profiles(con):
    with open(config.STIMULI_MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    con.executemany(
        "INSERT OR REPLACE INTO profiles(profile_id, display_name, age, bio, image_file, image_sha256) "
        "VALUES (?,?,?,?,?,?)",
        [(m["profile_id"], m["display_name"], m["age"], m["bio"], m["image_file"], m["image_sha256"])
         for m in manifest])
    con.commit()


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
