### Deepest level: median time per operation, and the copy's flat graph

| library | tt | bdd | sat | sat_clauses | sat_hybrid | copy |
| ------- | -- | --- | --- | ----------- | ---------- | ---- |
| deep_e3_l2 | 16.7 µs | 107 µs | 72.3 µs | 2.77 ms | 85.5 µs | 8.6 µs, 60 nodes |
| deep_e3_l4 | 12.1 µs | 99 µs | 43.9 µs | 45.9 µs | 44.4 µs | 60.2 µs, 507 nodes |
| deep_e3_l6 | 12.8 µs | 106 µs | 43.4 µs | 46.2 µs | 44.5 µs | 462 µs, 4,541 nodes |
| deep_e3_l8 | 12.7 µs | 104 µs | 45.6 µs | 47.2 µs | 45.5 µs | 3.55 ms, 39,773 nodes |
| deep_e3_l10 | 13.3 µs | 103 µs | 47.9 µs | 48.9 µs | 48.2 µs | 31.8 ms, 361,225 nodes |
| deep_e3_l12 | 15.7 µs | 114 µs | 68.3 µs | 2.11 ms | 81.2 µs | 307 ms, 3,245,020 nodes |
| deep_e3_l14 | 12.9 µs | 102 µs | 49.1 µs | 50.7 µs | 46.5 µs | 6.1 µs, 12 nodes (6 of 7 past the limit) |
| deep_e4_l2 | 17.9 µs | 102 µs | 67.7 µs | 137 µs | 68.2 µs | 10.4 µs, 71 nodes |
| deep_e4_l4 | 21.9 µs | 103 µs | 163 µs | 8.73 ms | 131 µs | 126 µs, 1,064 nodes |
| deep_e4_l6 | 16.3 µs | 102 µs | 58.9 µs | 62.6 µs | 59.4 µs | 1.65 ms, 17,466 nodes |
| deep_e4_l8 | 17.3 µs | 103 µs | 68 µs | 69.4 µs | 66 µs | 24.2 ms, 277,872 nodes |
| deep_e4_l10 | 16.4 µs | 102 µs | 64 µs | 64.9 µs | 61.7 µs | 393 ms, 4,520,950 nodes |
| deep_e4_l12 | 16 µs | 102 µs | 58 µs | 58 µs | 57.7 µs | 6.8 µs, 15 nodes (6 of 11 past the limit) |
| deep_e4_l14 | 16.8 µs | 114 µs | 60.2 µs | 58.6 µs | 97.7 µs | 5.19 µs, 12 nodes (6 of 9 past the limit) |
| wide_v12 | 54.1 µs | 102 µs | 100 µs | 2.31 ms | 101 µs | 9.04 ms, 39,373 nodes |
| wide_v16 | 526 µs | 98.4 µs | 613 µs | 646 µs | 644 µs | 5.42 ms, 39,377 nodes |
| wide_v20 | 12.6 ms | 103 µs | 12.5 ms | timeout | 12.4 ms | 4.69 ms, 39,381 nodes |

### Whole library: total time, SAT refinements, and agreement

| library | tt | bdd | sat | sat_clauses | sat_hybrid | copy | methods that finished agree |
| ------- | -- | --- | --- | ----------- | ---------- | ---- | --------------------------- |
| deep_e3_l2 | 114 µs | 1.7 ms | 484 µs, 13 refinements | 16 ms, 6,881 refinements | 567 µs, 71 refinements | 79.2 µs | True, planted 6/6 |
| deep_e3_l4 | 287 µs | 4.21 ms | 1.3 ms, 56 refinements | 53 ms, 19,172 refinements | 1.5 ms, 247 refinements | 629 µs | True, planted 10/10 |
| deep_e3_l6 | 469 µs | 6.66 ms | 2.34 ms, 164 refinements | 48.4 ms, 21,918 refinements | 2.59 ms, 483 refinements | 4.55 ms | True, planted 14/14 |
| deep_e3_l8 | 651 µs | 7.97 ms | 2.96 ms, 162 refinements | 77 ms, 28,154 refinements | 3.03 ms, 332 refinements | 33.7 ms | True, planted 17/17 |
| deep_e3_l10 | 820 µs | 10.2 ms | 4.76 ms, 386 refinements | 80.6 ms, 33,182 refinements | 4.16 ms, 584 refinements | 308 ms | True, planted 20/20 |
| deep_e3_l12 | 991 µs | 12.4 ms | 4.36 ms, 179 refinements | 121 ms, 48,830 refinements | 4.75 ms, 634 refinements | 2.71 s | True, planted 28/28 |
| deep_e3_l14 | 1.12 ms | 12.7 ms | 5.4 ms, 322 refinements | 86.4 ms, 31,918 refinements | 4.75 ms, 377 refinements | 7.58 s (6 unfinished) | True, planted 19/19 |
| deep_e4_l2 | 134 µs | 1.75 ms | 602 µs, 16 refinements | 19.2 ms, 8,025 refinements | 658 µs, 81 refinements | 97.3 µs | True, planted 4/4 |
| deep_e4_l4 | 391 µs | 3.71 ms | 2.11 ms, 194 refinements | 92.6 ms, 31,797 refinements | 2.34 ms, 578 refinements | 1.09 ms | True, planted 15/15 |
| deep_e4_l6 | 599 µs | 5.89 ms | 2.85 ms, 198 refinements | 49.3 ms, 23,221 refinements | 2.66 ms, 324 refinements | 15.4 ms | True, planted 14/14 |
| deep_e4_l8 | 886 µs | 8.24 ms | 9.78 ms, 1,708 refinements | 116 ms, 42,793 refinements | 4.98 ms, 1,067 refinements | 207 ms | True, planted 28/28 |
| deep_e4_l10 | 1.08 ms | 10 ms | 10.7 ms, 1,985 refinements | 130 ms, 53,277 refinements | 5.89 ms, 1,235 refinements | 3.29 s | True, planted 31/31 |
| deep_e4_l12 | 1.29 ms | 11.7 ms | 10.5 ms, 1,785 refinements | 140 ms, 60,051 refinements | 6.3 ms, 921 refinements | 12.8 s (6 unfinished) | True, planted 36/36 |
| deep_e4_l14 | 1.6 ms | 15.7 ms | 4.6 s, 151,400 refinements | 155 ms, 66,749 refinements | 13.5 ms, 3,281 refinements | 12.3 s (18 unfinished) | True, planted 48/48 |
| wide_v12 | 2.31 ms | 5.45 ms | 4.91 ms, 198 refinements | 392 ms, 100,549 refinements | 4.98 ms, 651 refinements | 82.4 ms | True, planted 0/0 |
| wide_v16 | 23.8 ms | 5.88 ms | 31.6 ms, 539 refinements | 31.4 s, 1,196,500 refinements | 31.3 ms, 967 refinements | 47.1 ms | True, planted 0/0 |
| wide_v20 | 530 ms | 5.41 ms | 525 ms, 288 refinements |  | 524 ms, 515 refinements | 45.1 ms | True, planted 0/0 |
