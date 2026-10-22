"""Scripted export: one row per participant, ready for analysis.

Usage: python export.py [--db data/study.db] [--out data/export.csv] [--include-test]
Raw data are never edited by hand; exclusions are flagged here with reasons."""
import argparse
import csv
import os

import config
import db

MIN_SECONDS_PER_PROFILE = 5  # provisional speeding threshold; fixed after the pilot


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
        reasons = []
        if p["status"] != "completed":
            reasons.append("incomplete")
        if r["auth_n_items"] < 18 or r["trust_n_items"] < 18:
            reasons.append("missing_ratings")
        if r["min_view_ms"] is not None and r["min_view_ms"] < MIN_SECONDS_PER_PROFILE * 1000:
            reasons.append("too_fast")
        r["exclude"] = int(bool(reasons))
        r["exclude_reason"] = ";".join(reasons)
        rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=config.DB_PATH)
    ap.add_argument("--out", default=os.path.join(config.BASE_DIR, "data", "export.csv"))
    ap.add_argument("--include-test", action="store_true")
    a = ap.parse_args()
    con = db.connect(a.db)
    rows = build_rows(con, a.include_test)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        if rows:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"Exported {len(rows)} participant rows to {a.out}")


if __name__ == "__main__":
    main()
