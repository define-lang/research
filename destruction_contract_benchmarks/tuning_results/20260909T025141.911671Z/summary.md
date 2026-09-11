Ratios relative to 256/1024; lower is better. Cases include scale and seed.
Only compare aggregate scores with equal coverage and no failures.

| Pair/control | Cases | Failures | CPU geomean | Peak RSS geomean | Worst CPU | Worst RSS |
| --- | --- | --- | --- | --- | --- | --- |
| 64/2048 | 7/7 | 0 | 0.992 | 0.979 | 1.179 (sparse_updates:s32:seed74921) | 1.447 (sparse_updates:s32:seed74921) |
| 256/1024 | 7/7 | 0 | 1.000 | 1.000 | 1.000 (sparse_updates:s32:seed74921) | 1.000 (sparse_updates:s32:seed74921) |
| 64/1024 | 7/7 | 0 | 1.011 | 0.992 | 1.024 (branch_updates:s32:seed74921) | 1.000 (older_caller_knowledge:s32:seed74921) |
| 64/4096 | 7/7 | 0 | 1.031 | 1.061 | 1.530 (sparse_updates:s32:seed74921) | 2.251 (sparse_updates:s32:seed74921) |
| 64/8192 | 7/7 | 0 | 1.182 | 1.303 | 2.324 (sparse_updates:s32:seed74921) | 3.911 (sparse_updates:s32:seed74921) |

## 256/1024

| Case | Scale | Seed | CPU ms (min-max) | Peak MiB | Additional retained MiB | Samples | Failures | CPU ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| batch_updates | 32 | 74921 | 1985.95 (1953.68-2004.41) | 3861.21 | 2916.88 | 3 | 0 | 1.000 |
| branch_updates | 32 | 74921 | 1419.70 (1413.83-1437.05) | 1191.41 | 559.54 | 3 | 0 | 1.000 |
| branching_callers | 32 | 74921 | 775.99 (768.61-784.33) | 375.12 | 167.39 | 3 | 0 | 1.000 |
| deep_callers | 32 | 74921 | 467.58 (465.78-500.95) | 320.80 | 188.37 | 3 | 0 | 1.000 |
| dense_callers | 32 | 74921 | 1454.32 (1406.09-1458.09) | 1537.57 | 702.44 | 3 | 0 | 1.000 |
| older_caller_knowledge | 32 | 74921 | 2049.60 (2046.05-2063.93) | 1150.92 | 708.19 | 3 | 0 | 1.000 |
| sparse_updates | 32 | 74921 | 694.54 (678.03-706.65) | 611.52 | 436.01 | 3 | 0 | 1.000 |

## 64/1024

| Case | Scale | Seed | CPU ms (min-max) | Peak MiB | Additional retained MiB | Samples | Failures | CPU ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| batch_updates | 32 | 74921 | 2009.22 (1982.79-2017.74) | 3860.83 | 2916.90 | 3 | 0 | 1.012 |
| branch_updates | 32 | 74921 | 1453.21 (1445.22-1472.38) | 1191.30 | 559.54 | 3 | 0 | 1.024 |
| branching_callers | 32 | 74921 | 792.11 (787.41-808.07) | 353.22 | 145.50 | 3 | 0 | 1.021 |
| deep_callers | 32 | 74921 | 465.17 (457.77-472.39) | 320.89 | 188.44 | 3 | 0 | 0.995 |
| dense_callers | 32 | 74921 | 1461.00 (1433.53-1476.90) | 1537.79 | 702.44 | 3 | 0 | 1.005 |
| older_caller_knowledge | 32 | 74921 | 2073.96 (2070.80-2090.01) | 1151.32 | 708.53 | 3 | 0 | 1.012 |
| sparse_updates | 32 | 74921 | 700.59 (699.72-707.24) | 611.52 | 436.08 | 3 | 0 | 1.009 |

## 64/4096

| Case | Scale | Seed | CPU ms (min-max) | Peak MiB | Additional retained MiB | Samples | Failures | CPU ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| batch_updates | 32 | 74921 | 1024.41 (1018.42-1045.59) | 1322.50 | 1070.46 | 3 | 0 | 0.516 |
| branch_updates | 32 | 74921 | 1506.36 (1475.35-1507.11) | 1396.31 | 730.23 | 3 | 0 | 1.061 |
| branching_callers | 32 | 74921 | 944.93 (929.38-955.21) | 562.32 | 354.64 | 3 | 0 | 1.218 |
| deep_callers | 32 | 74921 | 535.75 (521.94-541.69) | 457.95 | 325.57 | 3 | 0 | 1.146 |
| dense_callers | 32 | 74921 | 1521.12 (1502.99-1544.41) | 1512.27 | 689.57 | 3 | 0 | 1.046 |
| older_caller_knowledge | 32 | 74921 | 2081.23 (2077.07-2101.23) | 916.94 | 474.21 | 3 | 0 | 1.015 |
| sparse_updates | 32 | 74921 | 1062.45 (1058.64-1083.89) | 1376.38 | 1200.93 | 3 | 0 | 1.530 |

## 64/8192

| Case | Scale | Seed | CPU ms (min-max) | Peak MiB | Additional retained MiB | Samples | Failures | CPU ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| batch_updates | 32 | 74921 | 939.47 (935.95-962.28) | 989.91 | 737.90 | 3 | 0 | 0.473 |
| branch_updates | 32 | 74921 | 1679.74 (1665.55-1693.21) | 1657.40 | 991.43 | 3 | 0 | 1.183 |
| branching_callers | 32 | 74921 | 1110.96 (1106.48-1118.75) | 818.93 | 611.26 | 3 | 0 | 1.432 |
| deep_callers | 32 | 74921 | 666.47 (660.58-668.80) | 704.50 | 572.17 | 3 | 0 | 1.425 |
| dense_callers | 32 | 74921 | 1621.38 (1573.40-1622.34) | 1508.53 | 698.22 | 3 | 0 | 1.115 |
| older_caller_knowledge | 32 | 74921 | 2235.15 (2210.01-2237.62) | 1119.51 | 676.71 | 3 | 0 | 1.091 |
| sparse_updates | 32 | 74921 | 1614.30 (1601.17-1617.45) | 2391.78 | 2216.33 | 3 | 0 | 2.324 |
