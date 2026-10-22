"""Study configuration. Every value that affects data or allocation lives here
so it can be copied into the reproducibility record."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database (SQLite file). Override with STUDY_DB=/path/to/file.db
DB_PATH = os.environ.get("STUDY_DB", os.path.join(BASE_DIR, "data", "study.db"))

# Randomization: permuted blocks of size 4 (2 x label, 2 x no label)
RANDOM_SEED = int(os.environ.get("STUDY_SEED", "20261022"))
BLOCK_SIZE = 4
ALLOCATION_SLOTS = 400          # pre-generated sequence length per stream

# Conditions: 0 = no origin label, 1 = "AI-generated image" label
CONDITIONS = {0: "no_label", 1: "ai_label"}
LABEL_TEXT = "AI-generated image"

# Rating items (1-7 agreement). Construct codes are used by the analysis script.
ITEMS = [
    (1, "AUTH", "This profile seems genuine."),
    (2, "AUTH", "This person's self-presentation seems believable."),
    (3, "AUTH", "This profile seems sincere."),
    (4, "TRUST", "This person seems trustworthy."),
    (5, "TRUST", "This person seems honest."),
    (6, "TRUST", "This person seems reliable."),
]
SCALE_MIN, SCALE_MAX = 1, 7

STIMULI_DIR = os.path.join(BASE_DIR, "static", "stimuli")
STIMULI_MANIFEST = os.path.join(STIMULI_DIR, "manifest.json")
