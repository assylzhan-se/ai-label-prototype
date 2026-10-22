"""Initial functional tests T1-T4 (Section 9.3 of the report)."""
import hashlib
import json
import os
import re

import config
import export
from conftest import ELIGIBLE, article_html, enrol

LABEL_SPAN = re.compile(r'<span class="origin-label"[^>]*>[^<]*</span>')


def condition_of(con, code):
    return con.execute("SELECT condition FROM participants WHERE study_code=?", (code,)).fetchone()[0]


# ---------------- T1: label visibility by condition ----------------
def test_T1_label_shown_only_in_label_condition(client, con):
    seen = {0: 0, 1: 0}
    for _ in range(8):                       # two full blocks -> both conditions present
        code = enrol(client)
        cond = condition_of(con, code)
        for pos in range(1, 7):
            html = client.get(f"/s/{code}/profile/{pos}").get_data(as_text=True)
            has_label = config.LABEL_TEXT in html
            assert has_label == (cond == 1), f"{code} cond={cond} pos={pos}"
            seen[cond] += 1
    assert seen[0] == 24 and seen[1] == 24


# ---------------- T2: content equality across conditions ----------------
def test_T2a_stimulus_hashes_match_manifest(con):
    with open(config.STIMULI_MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert len(manifest) == 6
    for m in manifest:
        with open(os.path.join(config.STIMULI_DIR, m["image_file"]), "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == m["image_sha256"]
        row = con.execute("SELECT image_sha256 FROM profiles WHERE profile_id=?", (m["profile_id"],)).fetchone()
        assert row[0] == m["image_sha256"]


def test_T2b_profile_markup_identical_except_label(client, con):
    cards = {0: {}, 1: {}}
    for _ in range(4):
        code = enrol(client)
        cond = condition_of(con, code)
        for pos in range(1, 7):
            html = client.get(f"/s/{code}/profile/{pos}").get_data(as_text=True)
            card = article_html(html)
            pid = re.search(r'data-profile="(P\d)"', card).group(1)
            cards[cond][pid] = LABEL_SPAN.sub("", card)
    assert set(cards[0]) == set(cards[1]) == {f"P{i}" for i in range(1, 7)}
    for pid in cards[0]:
        assert cards[0][pid] == cards[1][pid], f"markup differs for {pid}"


# ---------------- T3: allocation balance ----------------
def test_T3_block_randomization_balance(client, con):
    conds = [condition_of(con, enrol(client)) for _ in range(100)]
    assert conds.count(0) == 50 and conds.count(1) == 50
    running = 0
    for c in conds:
        running += 1 if c == 1 else -1
        assert abs(running) <= config.BLOCK_SIZE // 2
    for i in range(0, 100, 4):
        assert sum(conds[i:i + 4]) == 2
    # test sessions never consume the real allocation stream
    assert con.execute("SELECT COUNT(*) FROM allocation WHERE stream='real' AND used_by IS NOT NULL").fetchone()[0] == 0
    # every participant is marked as test data
    assert con.execute("SELECT COUNT(*) FROM participants WHERE is_test=0").fetchone()[0] == 0


# ---------------- T4: data saving ----------------
def complete_session(client, code, values):
    for pos in range(1, 7):
        form = {f"item{n}": str(values[(pos, n)]) for n in range(1, 7)}
        form["decision"] = "like" if pos % 2 else "skip"
        r = client.post(f"/s/{code}/profile/{pos}", data=form)
        assert r.status_code == 302
        client.post("/api/events", json={"study_code": code, "events": [
            {"type": "view_start", "profile_id": f"x{pos}", "ts": 1},
            {"type": "view_end", "profile_id": f"x{pos}", "value_ms": 9000 + pos, "ts": 2}]})
    r = client.post(f"/s/{code}/post", data={"label_recall": "yes", "open_text": "test session"})
    assert r.status_code == 302 and r.location.endswith("/debrief")


def test_T4_ratings_saved_with_correct_code_and_condition(client, con):
    code = enrol(client)
    values = {(pos, n): ((pos + n) % 7) + 1 for pos in range(1, 7) for n in range(1, 7)}
    complete_session(client, code, values)

    rows = con.execute("SELECT * FROM ratings WHERE study_code=?", (code,)).fetchall()
    assert len(rows) == 36
    order = con.execute("SELECT profile_order FROM participants WHERE study_code=?", (code,)).fetchone()[0].split(",")
    for r in rows:
        assert r["profile_id"] == order[r["position"] - 1]
        assert r["value"] == values[(r["position"], r["item_no"])]
        assert r["construct"] == ("AUTH" if r["item_no"] <= 3 else "TRUST")
    p = con.execute("SELECT * FROM participants WHERE study_code=?", (code,)).fetchone()
    a = con.execute("SELECT * FROM allocation WHERE used_by=?", (code,)).fetchone()
    assert p["status"] == "completed" and p["condition"] == a["condition"] and p["is_test"] == 1
    assert con.execute("SELECT COUNT(*) FROM events WHERE study_code=?", (code,)).fetchone()[0] == 12
    assert con.execute("SELECT label_recall FROM post_survey WHERE study_code=?", (code,)).fetchone()[0] == "yes"

    # scripted export reproduces the participant-level scale scores
    row = [r for r in export.build_rows(con, include_test=True) if r["study_code"] == code][0]
    exp_auth = sum(v for (pos, n), v in values.items() if n <= 3) / 18
    exp_trust = sum(v for (pos, n), v in values.items() if n > 3) / 18
    assert abs(row["auth_score"] - exp_auth) < 1e-3 and abs(row["trust_score"] - exp_trust) < 1e-3
    assert row["exclude"] == 0 and row["likes"] == 3


def test_T4b_invalid_or_incomplete_input_not_saved(client, con):
    code = enrol(client)
    bad = {f"item{n}": "4" for n in range(1, 7)}
    bad["item3"] = "8"
    bad["decision"] = "like"
    r = client.post(f"/s/{code}/profile/1", data=bad)
    assert "error=incomplete" in r.location
    del bad["item3"]
    client.post(f"/s/{code}/profile/1", data=bad)
    assert con.execute("SELECT COUNT(*) FROM ratings WHERE study_code=?", (code,)).fetchone()[0] == 0


def test_T4c_ineligible_or_no_consent_stores_nothing(client, con):
    client.post("/consent", data=dict(ELIGIBLE, age_18_25="no"))
    client.post("/consent", data=dict(ELIGIBLE, consent="no"))
    assert con.execute("SELECT COUNT(*) FROM participants").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM consent_records").fetchone()[0] == 0
