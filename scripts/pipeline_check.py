"""End-to-end pipeline check with SIMULATED, test-marked sessions (v4).

Drives the real app (consent with gender -> stratified randomization -> ratings incl. attention item ->
events -> two-part manipulation check) for N simulated sessions with random answers, then runs
export.py. The resulting numbers only show that the pipeline runs; they are not study data and
must never be reported as results. Usage: python scripts/pipeline_check.py [N]"""
import csv
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
from app import create_app  # noqa: E402
from conftest import ELIGIBLE  # noqa: E402
import config  # noqa: E402
import db  # noqa: E402
import export  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
out_dir = os.path.join(ROOT, "data", "pipeline_check")
os.makedirs(out_dir, exist_ok=True)
dbp = os.path.join(out_dir, "pipeline_check.db")
if os.path.exists(dbp):
    os.remove(dbp)
rng = random.Random(7)
app = create_app(db_path=dbp, min_seconds=0)
for i in range(N):
    c = app.test_client()                    # each simulated participant uses a fresh browser
    r = c.post("/consent", data=dict(ELIGIBLE, gender=rng.choice(["F", "M", "N"])))
    code = r.location.split("/")[2]
    person = rng.gauss(4, 1)                     # simulated rater tendency, no label effect built in
    for pos in range(1, 9):
        form = {f"item{n}": str(min(7, max(1, round(person + rng.gauss(0, 0.9))))) for n in range(1, 7)}
        form["decision"] = rng.choice(["like", "skip"])
        if pos == config.ATTENTION_POSITION:
            form["attn"] = "2" if rng.random() > 0.1 else "5"
        c.get(f"/s/{code}/profile/{pos}")
        c.post(f"/s/{code}/profile/{pos}", data=form)
        c.post("/api/events", json={"study_code": code, "events": [
            {"type": "view_end", "profile_id": None, "value_ms": rng.randint(10000, 40000), "ts": 0}]})
    if i == N - 1:
        break                                    # last session left incomplete on purpose
    c.post(f"/s/{code}/post", data={"label_recall": rng.choice(["yes", "yes", "no", "not_sure"]),
                                    "label_text": rng.choice(["ai", "ai", "none", "verified"]),
                                    "open_text": rng.choice(["", "", "simulated answer"]),
                                    "study_year": rng.choice(["1", "2", "3", "4+"]),
                                    "app_use_freq": rng.choice(["Rarely", "Monthly", "Weekly"])})
con = db.connect(dbp)
rows = export.build_rows(con, include_test=True)
with open(os.path.join(out_dir, "export_pipeline_check.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(f"Simulated {N} test sessions -> {out_dir}/export_pipeline_check.csv")
