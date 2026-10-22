# AI-image label experiment — dating-app research prototype

Research Methods and Tools, Assignment 3 (AITU, SE-2428). Two-arm between-subjects
experiment: profiles with an "AI-generated image" label vs. the same profiles with no label.

## Run

```bash
pip install -r requirements.txt
python -m playwright install chromium      # only needed for browser tests / screenshots
python scripts/make_placeholder_stimuli.py # creates 6 placeholder images + manifest (SHA-256)
python app.py                              # http://127.0.0.1:5000  (add ?test=1 for a marked test session)
```

## Test (T1–T6)

```bash
python -m pytest -v -rxs tests/
```

| ID  | What it checks |
|-----|----------------|
| T1  | Label is rendered on all 6 profiles in the label condition and on none in the no-label condition |
| T2a | Image files match the manifest SHA-256 hashes and the database |
| T2b | Profile card markup is byte-identical across conditions once the label element is removed |
| T2c | Rendered geometry (photo, label slot, text) is identical in both conditions (desktop + 360 px phone) |
| T3  | 100 test enrolments: 50/50, every block of 4 is 2/2, imbalance never > 2, real stream untouched |
| T4  | Full session saves 36 ratings, 12 events and the post-survey under the right study code and condition; export reproduces scale scores |
| T4b | Out-of-range (8) or missing answers are rejected and nothing is stored |
| T4c | Ineligible or non-consenting visitors leave no record |
| T5  | Label is visible without scrolling on a 360×640 phone |
| T6  | **Known issue (xfail):** 1–7 radio buttons are 13×13 px / 21 px cells on a 360 px phone, below the WCAG 2.2 24×24 px minimum |

## Data and analysis

```bash
python export.py --out data/export.csv                       # one row per participant, exclusion flags
python analysis/analyze.py data/export.csv                   # alpha, Welch CI, Hedges g, Holm, Mann-Whitney
python scripts/pipeline_check.py 40                          # SIMULATED test sessions — pipeline check only
python analysis/analyze.py data/pipeline_check/export_pipeline_check.csv --pipeline-check
```

The pipeline-check numbers come from simulated test sessions and are **not study results**.

## Layout

```
app.py              Flask routes: consent → randomization → profiles/ratings → events → post → debrief
randomization.py    permuted blocks (size 4), separate real/test streams, per-participant profile order
db.py               SQLite schema (consent records separate from responses)
config.py           seed, block size, items, label text
export.py           scripted export + exclusion flags
analysis/analyze.py planned analysis for Objectives 2–3
templates/, static/ frontend (HTML/CSS, events.js)
tests/              T1–T6
docs/               architecture.png, erd.png, screenshots/, test_output.txt, REPRODUCIBILITY.md
```

## Before data collection

1. Replace `static/stimuli/P1–P6.png` with the final licensed synthetic face images (same names), then
   `python scripts/make_placeholder_stimuli.py --manifest-only` to recompute hashes; rerun the tests.
2. Fix the T6 tap-target issue.
3. Obtain ethics/instructor approval. Run real sessions without `?test=1`.
