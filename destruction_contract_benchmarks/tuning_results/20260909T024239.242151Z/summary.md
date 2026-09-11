Ratios relative to 256/1024; lower is better. Cases include scale and seed.
Only compare aggregate scores with equal coverage and no failures.

| Pair/control | Cases | Failures | CPU geomean | Peak RSS geomean | Worst CPU | Worst RSS |
| --- | --- | --- | --- | --- | --- | --- |
| 256/1024 | 12/14 | 2 | 1.000 | 1.000 | 1.000 (sparse_updates:s32:seed28413) | 1.000 (sparse_updates:s32:seed28413) |
| 64/1024 | 12/14 | 2 | 1.002 | 0.986 | 1.075 (branching_callers:s32:seed28413) | 1.001 (older_caller_knowledge:s16:seed28413) |
| 64/512 | 10/14 | 3 | 1.004 | 0.987 | 1.112 (deep_callers:s16:seed28413) | 1.285 (older_caller_knowledge:s16:seed28413) |
| 64/256 | 10/14 | 3 | 1.010 | 1.152 | 1.169 (deep_callers:s32:seed28413) | 1.914 (deep_callers:s32:seed28413) |
| 64/2048 | 12/14 | 1 | 1.030 | 1.053 | 1.187 (sparse_updates:s16:seed28413) | 1.506 (sparse_updates:s16:seed28413) |
| 64/4096 | 12/14 | 0 | 1.115 | 1.230 | 1.582 (sparse_updates:s16:seed28413) | 2.358 (sparse_updates:s16:seed28413) |
| 64/8192 | 10/14 | 2 | 1.299 | 1.525 | 2.427 (sparse_updates:s16:seed28413) | 4.088 (sparse_updates:s16:seed28413) |

## 256/1024

| Case | Scale | Seed | CPU ms (min-max) | Peak MiB | Additional retained MiB | Samples | Failures | CPU ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| batch_updates | 16 | 28413 | 606.58 (606.58-606.58) | 1040.71 | 901.72 | 1 | 0 | 1.000 |
| batch_updates | 32 | 28413 | inf (inf-inf) | inf | inf | 0 | 1 | nan |
| branch_updates | 16 | 28413 | 694.12 (694.12-694.12) | 604.45 | 260.61 | 1 | 0 | 1.000 |
| branch_updates | 32 | 28413 | 1436.04 (1436.04-1436.04) | 1192.60 | 560.82 | 1 | 0 | 1.000 |
| branching_callers | 16 | 28413 | 409.07 (409.07-409.07) | 211.51 | 95.08 | 1 | 0 | 1.000 |
| branching_callers | 32 | 28413 | 789.75 (789.75-789.75) | 375.17 | 167.64 | 1 | 0 | 1.000 |
| deep_callers | 16 | 28413 | 187.59 (187.59-187.59) | 148.20 | 69.99 | 1 | 0 | 1.000 |
| deep_callers | 32 | 28413 | 462.42 (462.42-462.42) | 320.77 | 188.38 | 1 | 0 | 1.000 |
| dense_callers | 16 | 28413 | 662.89 (662.89-662.89) | 761.34 | 321.06 | 1 | 0 | 1.000 |
| dense_callers | 32 | 28413 | inf (inf-inf) | inf | inf | 0 | 1 | nan |
| older_caller_knowledge | 16 | 28413 | 980.91 (980.91-980.91) | 438.53 | 204.41 | 1 | 0 | 1.000 |
| older_caller_knowledge | 32 | 28413 | 2095.34 (2095.34-2095.34) | 1150.83 | 708.77 | 1 | 0 | 1.000 |
| sparse_updates | 16 | 28413 | 314.16 (314.16-314.16) | 295.00 | 194.50 | 1 | 0 | 1.000 |
| sparse_updates | 32 | 28413 | 744.06 (744.06-744.06) | 611.50 | 436.07 | 1 | 0 | 1.000 |

## 64/4096

| Case | Scale | Seed | CPU ms (min-max) | Peak MiB | Additional retained MiB | Samples | Failures | CPU ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| batch_updates | 16 | 28413 | 387.67 (387.67-387.67) | 451.65 | 312.75 | 1 | 0 | 0.639 |
| batch_updates | 32 | 28413 | 1052.09 (1052.09-1052.09) | 1324.81 | 1072.39 | 1 | 0 | nan |
| branch_updates | 16 | 28413 | 717.06 (717.06-717.06) | 711.63 | 368.39 | 1 | 0 | 1.033 |
| branch_updates | 32 | 28413 | 1465.30 (1465.30-1465.30) | 1397.15 | 765.38 | 1 | 0 | 1.020 |
| branching_callers | 16 | 28413 | 460.17 (460.17-460.17) | 294.58 | 178.15 | 1 | 0 | 1.125 |
| branching_callers | 32 | 28413 | 950.31 (950.31-950.31) | 562.36 | 354.90 | 1 | 0 | 1.203 |
| deep_callers | 16 | 28413 | 230.47 (230.47-230.47) | 236.70 | 157.81 | 1 | 0 | 1.229 |
| deep_callers | 32 | 28413 | 563.84 (563.84-563.84) | 457.97 | 325.51 | 1 | 0 | 1.219 |
| dense_callers | 16 | 28413 | 726.88 (726.88-726.88) | 750.95 | 319.17 | 1 | 0 | 1.097 |
| dense_callers | 32 | 28413 | 1604.75 (1604.75-1604.75) | 1512.88 | 690.61 | 1 | 0 | nan |
| older_caller_knowledge | 16 | 28413 | 1023.72 (1023.72-1023.72) | 443.41 | 209.30 | 1 | 0 | 1.044 |
| older_caller_knowledge | 32 | 28413 | 2124.76 (2124.76-2124.76) | 916.73 | 474.68 | 1 | 0 | 1.014 |
| sparse_updates | 16 | 28413 | 496.97 (496.97-496.97) | 695.50 | 595.06 | 1 | 0 | 1.582 |
| sparse_updates | 32 | 28413 | 1098.52 (1098.52-1098.52) | 1376.27 | 1200.97 | 1 | 0 | 1.476 |
