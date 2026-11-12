"""Scripted export: one row per participant, ready for analysis.

Usage: python export.py [--db data/study.db] [--out data/export.csv] [--include-test]
Raw data are never edited by hand; exclusions are flagged here with reasons."""
import argparse
import csv
import os

import config
import db

# Speeding rule, fixed before any outcome data were inspected (deviation from v1, see report):
# a participant is "too fast" if the MEAN viewing+rating time per profile is below 5 s.
# (v1 used the minimum over profiles, which excluded a whole session for one quick profile.)
MIN_MEAN_SECONDS_PER_PROFILE = 5


def build_rows(con, include_test=False):
    rows = []
    q = "SELECT * FROM participants" + ("" if include_test else " WHERE is_test=0") + " ORDER BY alloc_slot"
    for p in con.execute(q):
        code = p["study_code"]
        r = {"study_code": code, "condition": p["condition"], "condition_name": config.CONDITIONS[p["condition"]],
             "is_test": p["is_test"], "status": p["status"]}
        for construct in ("AUTH", "TRUST"):
            v = con.execute("SELECT AVG(value), COUNT(*) FROM ratings WHERE study_code=? AND construct=?",
                            (code, construct)).fetchone()
            r[f"{construct.lower()}_score"] = round(v[0], 4) if v[0] is not None else None
            r[f"{construct.lower()}_n_items"] = v[1]
        for n, _, _ in config.ITEMS:  # item means across profiles (for Cronbach's alpha)
            v = con.execute("SELECT AVG(value) FROM ratings WHERE study_code=? AND item_no=?", (code, n)).fetchone()[0]
            r[f"item{n}"] = round(v, 4) if v is not None else None
        r["likes"] = con.execute("SELECT COUNT(DISTINCT profile_id) FROM ratings WHERE study_code=? AND decision='like'",
                                 (code,)).fetchone()[0]
        vt = con.execute("SELECT AVG(value_ms), MIN(value_ms) FROM events WHERE study_code=? AND event_type='view_end'",
                         (code,)).fetchone()
        r["mean_view_ms"] = round(vt[0]) if vt[0] is not None else None
        r["min_view_ms"] = vt[1]
        ps = con.execute("SELECT * FROM post_survey WHERE study_code=?", (code,)).fetchone()
        r["label_recall"] = ps["label_recall"] if ps else None
        for k in ("gender", "study_year", "app_use_freq"):
            r[k] = ps[k] if ps else None
        r["has_open_text"] = int(bool(ps and ps["open_text"]))
        r["label_hovers"] = con.execute("SELECT COUNT(*) FROM events WHERE study_code=? AND event_type IN ('label_hover','label_click')",
                                        (code,)).fetchone()[0]
        r["created_at"] = p["created_at"]; r["completed_at"] = p["completed_at"]
        reasons = []
        if p["status"] != "completed":
            reasons.append("incomplete")
        if r["auth_n_items"] < 18 or r["trust_n_items"] < 18:
            reasons.append("missing_ratings")
        if r["mean_view_ms"] is not None and r["mean_view_ms"] < MIN_MEAN_SECONDS_PER_PROFILE * 1000:
            reasons.append("too_fast")
        # Quality flag (reported, used only in a sensitivity analysis): identical answer to all 36 items
        sd = con.execute("SELECT COUNT(DISTINCT value) FROM ratings WHERE study_code=?", (code,)).fetchone()[0]
        r["straightlining"] = int(r["auth_n_items"] + r["trust_n_items"] == 36 and sd == 1)
        r["exclude"] = int(bool(reasons))
        r["exclude_reason"] = ";".join(reasons)
        rows.append(r)
    return rows


def build_rating_rows(con, include_test=False):
    """Long format: one row per participant x profile (profile-level scale means)."""
    q = """SELECT r.study_code, p.condition, p.is_test, r.profile_id, r.position,
                  AVG(CASE WHEN r.construct='AUTH' THEN r.value END) AS auth,
                  AVG(CASE WHEN r.construct='TRUST' THEN r.value END) AS trust,
                  MAX(r.decision) AS decision
           FROM ratings r JOIN participants p USING (study_code)""" + \
        ("" if include_test else " WHERE p.is_test=0") + \
        " GROUP BY r.study_code, r.profile_id ORDER BY p.alloc_slot, r.position"
    return [dict(x) for x in con.execute(q)]


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        if rows:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=config.DB_PATH)
    ap.add_argument("--out", default=os.path.join(config.BASE_DIR, "data", "export.csv"))
    ap.add_argument("--include-test", action="store_true")
    a = ap.parse_args()
    con = db.connect(a.db)
    rows = build_rows(con, a.include_test)
    write_csv(a.out, rows)
    long_path = a.out.replace(".csv", "_profile_level.csv")
    write_csv(long_path, build_rating_rows(con, a.include_test))
    print(f"Exported {len(rows)} participant rows to {a.out} (+ {long_path})")


if __name__ == "__main__":
    main()
