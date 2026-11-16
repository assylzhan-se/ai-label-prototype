"""Study configuration. Every value that affects data or allocation lives here
so it can be copied into the reproducibility record."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database (SQLite file). Override with STUDY_DB=/path/to/file.db
# Wave 2 (v4, final study) uses a fresh database so wave-1 pilot data stay untouched.
DB_PATH = os.environ.get("STUDY_DB", os.path.join(BASE_DIR, "data", "study_wave2.db"))
WAVE = int(os.environ.get("STUDY_WAVE", "2"))

# v4 data-quality settings (response to Assignment 4 feedback)
MIN_SECONDS_PER_PROFILE = 10      # Next button enabled and server accepts a profile only after this time
ATTENTION_POSITION = 3            # profile position that carries the attention-check statement
ATTENTION_TEXT = "To show that you are reading carefully, please select 2 for this statement."
ATTENTION_CORRECT = 2
GENDER_STRATA = ("F", "M", "N")   # female, male, not stated -> separate allocation streams
LABEL_TEXT_OPTIONS = [("ai", "AI-generated image"), ("verified", "Verified photo"),
                      ("edited", "Edited photo"), ("none", "I did not see a label")]

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
