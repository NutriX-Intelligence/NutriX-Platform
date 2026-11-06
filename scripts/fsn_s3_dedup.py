"""S3: cross-split near-duplicate check (pHash, Hamming <= 6) over dataset/custom_training_data."""
import csv
import json
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "dataset" / "custom_training_data"
OUT = ROOT / "docs" / "paper-upgrade" / "results" / "fsn"
THRESH = 6


def hashes(split):
    names, bits = [], []
    for p in sorted((DATA / split / "images").iterdir()):
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        try:
            h = imagehash.phash(Image.open(p).convert("RGB"))
        except Exception as e:
            print("skip", p.name, e)
            continue
        names.append(p.name)
        bits.append(h.hash.flatten())
    return names, np.array(bits, dtype=bool)


def nearest(a_bits, b_bits, chunk=16):
    """for every row of a: (min Hamming distance, index) against b"""
    dist, idx = [], []
    for s in range(0, len(a_bits), chunk):
        d = (a_bits[s:s + chunk, None, :] != b_bits[None, :, :]).sum(-1)
        idx.append(d.argmin(1))
        dist.append(d.min(1))
    return np.concatenate(dist), np.concatenate(idx)


H = {s: hashes(s) for s in ("train", "valid", "test")}
summary = {"hash": "imagehash.phash 64-bit", "threshold_hamming_le": THRESH,
           "n_images": {s: len(H[s][0]) for s in H}}
rows = []
for a, b in (("test", "train"), ("valid", "train"), ("test", "valid")):
    dist, idx = nearest(H[a][1], H[b][1])
    n_dup = int((dist <= THRESH).sum())
    summary[f"{a}_vs_{b}"] = {"n_with_near_dup": n_dup, "n": len(dist), "pct": round(100 * n_dup / len(dist), 2),
                              "exact_hash_match_d0": int((dist == 0).sum())}
    for i, (d_, j) in enumerate(zip(dist, idx)):
        rows.append(dict(query_split=a, query_image=H[a][0][i], ref_split=b, nearest_image=H[b][0][j],
                         hamming=int(d_), near_dup=int(d_ <= THRESH)))
OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / "S3_dedup.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
(OUT / "S3_dedup_summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
