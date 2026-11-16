"""v4 tests: responses to the Assignment 4 feedback (manipulation check, fast shared-device responses)."""
import os
import sys

import config
from app import create_app
from conftest import ELIGIBLE, enrol


def cond(con, code):
    return con.execute("SELECT condition, gender FROM participants WHERE study_code=?", (code,)).fetchone()


def test_T8_gender_stratified_balance(client, con):
    """Each gender has its own permuted-block stream, so gender cannot pile up in one condition."""
    for i in range(40):
        for g in ("F", "M"):
            client.post("/consent", data=dict(ELIGIBLE, gender=g))
    for g in ("F", "M"):
        rows = con.execute("SELECT condition FROM participants WHERE gender=?", (g,)).fetchall()
        assert len(rows) == 40 and sum(r[0] for r in rows) == 20
    r = client.post("/consent", data={k: v for k, v in ELIGIBLE.items() if k != "gender"})
    assert b"including gender" in r.data          # gender is required before allocation


def test_T9_server_rejects_too_fast_profiles(tmp_path):
    app = create_app(db_path=str(tmp_path / "t9.db"), min_seconds=10)
    c = app.test_client()
    code = enrol(c)
    c.get(f"/s/{code}/profile/1")
    form = {f"item{n}": "4" for n in range(1, 7)}; form["decision"] = "like"
    r = c.post(f"/s/{code}/profile/1", data=form)
    assert "error=too_fast" in r.location
    html = c.get(f"/s/{code}/profile/1").get_data(as_text=True)
    assert 'data-min="10"' in html               # Next button disabled client-side for 10 s


def test_T10_attention_item_required_and_stored(client, con):
    code = enrol(client)
    order_pos = config.ATTENTION_POSITION
    for pos in range(1, order_pos):
        client.get(f"/s/{code}/profile/{pos}")
        client.post(f"/s/{code}/profile/{pos}", data=dict({f"item{n}": "4" for n in range(1, 7)}, decision="skip"))
    html = client.get(f"/s/{code}/profile/{order_pos}").get_data(as_text=True)
    assert config.ATTENTION_TEXT in html
    form = dict({f"item{n}": "4" for n in range(1, 7)}, decision="skip")
    assert "error=incomplete" in client.post(f"/s/{code}/profile/{order_pos}", data=form).location
    client.post(f"/s/{code}/profile/{order_pos}", data=dict(form, attn="2"))
    assert con.execute("SELECT attention_value FROM participants WHERE study_code=?", (code,)).fetchone()[0] == 2


def test_T11_two_part_manipulation_check(client, con):
    code = enrol(client)
    r = client.post(f"/s/{code}/post", data={"label_recall": "yes"})
    assert b"first two questions" in r.data       # label wording is required
    client.post(f"/s/{code}/post", data={"label_recall": "yes", "label_text": "verified"})
    row = con.execute("SELECT label_recall, label_text, gender FROM post_survey WHERE study_code=?", (code,)).fetchone()
    assert tuple(row) == ("yes", "verified", "Female")


def test_T12_one_participation_per_browser(client, con):
    r = client.post("/consent", data=dict(ELIGIBLE, is_test="0"))
    code = r.location.split("/")[2]
    client.get(f"/s/{code}/debrief")                # completion sets the cookie
    assert b"already taken part" in client.get("/").data
    assert b"Profile impressions study" in client.get("/?test=1").data   # team testing still possible
    dt = con.execute("SELECT device_token, source FROM participants WHERE study_code=?", (code,)).fetchone()
    assert dt[0] and dt[1] == "link"


def test_T13_real_photo_block_last_and_excluded_from_main_scores(client, con):
    import export
    for _ in range(4):
        code = enrol(client)
        order = con.execute("SELECT profile_order FROM participants WHERE study_code=?", (code,)).fetchone()[0].split(",")
        assert len(order) == 8 and sorted(order[6:]) == ["R1", "R2"] and all(p.startswith("P") for p in order[:6])
    for pos in range(1, 9):
        form = dict({f"item{n}": ("2" if pos <= 6 else "7") for n in range(1, 7)}, decision="like")
        if pos == config.ATTENTION_POSITION:
            form["attn"] = "2"
        client.get(f"/s/{code}/profile/{pos}")
        client.post(f"/s/{code}/profile/{pos}", data=form)
    row = [r for r in export.build_rows(con, include_test=True) if r["study_code"] == code][0]
    assert row["auth_score"] == 2 and row["trust_score"] == 2       # main scores: six AI profiles only
    assert row["real_auth"] == 7 and row["real_trust"] == 7         # exploratory block kept separately
