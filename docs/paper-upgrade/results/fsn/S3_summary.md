# S3: cross-split near-duplicate check (generated)

pHash (64-bit), near-duplicate = Hamming <= 6. Images: {'train': 51535, 'valid': 2484, 'test': 2128}.

| pair | queries | with near-dup | % | exact-hash (d=0) |
|---|---|---|---|---|
| test_vs_train | 2128 | 834 | 39.19 | 773 |
| valid_vs_train | 2484 | 815 | 32.81 | 737 |
| test_vs_valid | 2128 | 27 | 1.27 | 17 |

Leak-free rescoring of the S2 systems is in S2_summary.md (subsets `leak_free*`, test images with no train near-duplicate).
