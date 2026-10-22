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
    for stream, s in (("real", seed), ("test", seed + 1)):
        n = con.execute("SELECT COUNT(*) FROM allocation WHERE stream=?", (stream,)).fetchone()[0]
        if n == 0:
            con.executemany(
                "INSERT INTO allocation(stream, slot, block_no, condition) VALUES (?,?,?,?)",
                [(stream, slot, b, c) for slot, b, c in generate_sequence(s, n_slots)],
            )
    con.commit()


def assign_next(con, study_code, is_test):
    """Atomically take the next unused slot of the stream."""
    stream = "test" if is_test else "real"
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
    ids = sorted(profile_ids)
    random.Random(f"{seed}:{study_code}").shuffle(ids)
    return ids
