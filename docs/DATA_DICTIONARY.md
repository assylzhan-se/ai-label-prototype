# Data dictionary

## Participant-level export (`export.py` → CSV, one row per participant)

| Variable | Type | Values / meaning |
|---|---|---|
| study_code | text | Random code `P-XXXXXX`; the only identifier |
| condition | int | 0 = no label, 1 = "AI-generated image" label (independent variable) |
| condition_name | text | `no_label` / `ai_label` |
| is_test | int | 1 = team/automated test session (always excluded from analysis) |
| status | text | `started`, `rated`, `completed` |
| auth_score | float 1–7 | Mean of items 1–3 over 6 profiles (perceived authenticity, DV1) |
| trust_score | float 1–7 | Mean of items 4–6 over 6 profiles (perceived trustworthiness, DV2) |
| auth_n_items / trust_n_items | int | Number of stored ratings (complete = 18) |
| item1 … item6 | float 1–7 | Item mean over 6 profiles (for Cronbach's alpha) |
| likes | int 0–6 | Profiles with "Like" (exploratory log measure) |
| mean_view_ms / min_view_ms | int | Viewing time per profile from `view_end` events (exploratory; speeding check) |
| label_recall | text | `yes` / `no` / `not_sure` (manipulation check) |
| exclude | int | 1 = excluded from main analysis |
| exclude_reason | text | `incomplete`; `missing_ratings`; `too_fast` (min view < 5 s, provisional) |

## Database tables (`db.py`)

| Table | Content |
|---|---|
| allocation | Pre-generated permuted-block sequence (stream real/test, slot, block, condition, used_by) |
| participants | study_code, condition, allocation slot, is_test, profile order, status, timestamps |
| consent_records | Consent and eligibility confirmation per study code (kept separate from responses) |
| profiles | 6 fictional profiles: name, age, bio, image file, SHA-256 |
| ratings | One row per participant × profile × item: value 1–7, construct, position shown, like/skip |
| events | view_start, view_end (ms), like, skip, label_hover, label_click |
| post_survey | label_recall, optional open text, optional gender / year of study / app-use frequency |

Not collected: names, e-mail, IP address, photos, contacts, sexual orientation, relationship history.
