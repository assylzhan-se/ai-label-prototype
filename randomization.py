"""Permuted-block randomization and per-participant profile order.

The allocation sequence is generated once from a fixed seed and stored in the
database, so the order of assignments can be audited after data collection.
Test sessions use a separate stream so they never consume real slots."""
import random
import config


def generate_sequence(seed, n_slots, block_size=config.BLOCK_SIZE):
    """Return a list of (slot, block_no, condition)."""
    rng = random.Random(seed)
    seq = []
    block_no = 0
    while len(seq) < n_slots:
        block = [0] * (block_size // 2) + [1] * (block_size // 2)
        rng.shuffle(block)
        for c in block:
            seq.append((len(seq) + 1, block_no, c))
        block_no += 1
    return seq[:n_slots]


def ensure_allocation(con, seed=config.RANDOM_SEED, n_slots=config.ALLOCATION_SLOTS):
    streams = [("real", seed), ("test", seed + 1)]
    for i, g in enumerate(config.GENDER_STRATA):          # v4: stratified by gender
        streams += [(f"real_{g}", seed + 10 + i), (f"test_{g}", seed + 20 + i)]
    for stream, s in streams:
        n = con.execute("SELECT COUNT(*) FROM allocation WHERE stream=?", (stream,)).fetchone()[0]
        if n == 0:
            con.executemany(
                "INSERT INTO allocation(stream, slot, block_no, condition) VALUES (?,?,?,?)",
                [(stream, slot, b, c) for slot, b, c in generate_sequence(s, n_slots)],
            )
    con.commit()


def assign_next(con, study_code, is_test, stratum=None):
    """Atomically take the next unused slot of the stream (one stream per gender stratum in v4)."""
    stream = ("test" if is_test else "real") + (f"_{stratum}" if stratum else "")
    row = con.execute(
        "SELECT slot, condition FROM allocation WHERE stream=? AND used_by IS NULL "
        "ORDER BY slot LIMIT 1", (stream,)).fetchone()
    if row is None:
        raise RuntimeError("Allocation sequence exhausted")
    con.execute("UPDATE allocation SET used_by=? WHERE stream=? AND slot=?",
                (study_code, stream, row["slot"]))
    return row["slot"], row["condition"]


def profile_order(profile_ids, study_code, seed=config.RANDOM_SEED):
    """Individually randomized but reproducible order for one participant."""
    rng = random.Random(f"{seed}:{study_code}")
    main = sorted(i for i in profile_ids if not i.startswith("R"))
    real = sorted(i for i in profile_ids if i.startswith("R"))     # v4 exploratory block, always last
    rng.shuffle(main)
    rng.shuffle(real)
    return main + real
