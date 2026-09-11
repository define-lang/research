Ratios relative to 256/1024; lower is better. Cases include scale and seed.
Only compare aggregate scores with equal coverage and no failures.

| Pair/control | Cases | Failures | CPU geomean | Peak RSS geomean | Worst CPU | Worst RSS |
| --- | --- | --- | --- | --- | --- | --- |
| 1024/1024 | 4/4 | 0 | 0.951 | 1.537 | 1.201 (mixed_small:s4:seed28413) | 1.698 (mixed_medium:s4:seed74921) |
| 256/1024 | 4/4 | 0 | 1.000 | 1.000 | 1.000 (mixed_small:s4:seed74921) | 1.000 (mixed_small:s4:seed74921) |
| 512/1024 | 4/4 | 0 | 1.047 | 1.301 | 1.167 (mixed_small:s4:seed74921) | 1.393 (mixed_small:s4:seed74921) |
| 1024/4096 | 4/4 | 0 | 1.049 | 1.591 | 1.202 (mixed_small:s4:seed28413) | 1.849 (mixed_medium:s4:seed74921) |
| 256/2048 | 4/4 | 0 | 1.068 | 1.107 | 1.197 (mixed_medium:s4:seed74921) | 1.236 (mixed_medium:s4:seed28413) |
| 512/2048 | 4/4 | 0 | 1.202 | 1.405 | 1.302 (mixed_medium:s4:seed28413) | 1.435 (mixed_medium:s4:seed74921) |
| 256/4096 | 4/4 | 0 | 1.266 | 1.275 | 1.641 (mixed_medium:s4:seed74921) | 1.648 (mixed_medium:s4:seed28413) |
| 64/1024 | 4/4 | 0 | 1.282 | 1.224 | 1.362 (mixed_medium:s4:seed28413) | 1.515 (mixed_medium:s4:seed28413) |
| 512/4096 | 4/4 | 0 | 1.306 | 1.574 | 1.497 (mixed_medium:s4:seed28413) | 1.791 (mixed_medium:s4:seed28413) |

## 256/1024

| Case | Scale | Seed | CPU ms (min-max) | Peak MiB | Additional retained MiB | Samples | Failures | CPU ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed_medium | 4 | 28413 | 775.14 (770.19-779.08) | 414.02 | 353.26 | 3 | 0 | 1.000 |
| mixed_medium | 4 | 74921 | 678.13 (676.73-678.50) | 362.08 | 306.36 | 3 | 0 | 1.000 |
| mixed_small | 4 | 28413 | 290.83 (287.54-290.84) | 157.38 | 127.79 | 3 | 0 | 1.000 |
| mixed_small | 4 | 74921 | 321.21 (321.12-327.03) | 188.95 | 159.16 | 3 | 0 | 1.000 |

## 512/1024

| Case | Scale | Seed | CPU ms (min-max) | Peak MiB | Additional retained MiB | Samples | Failures | CPU ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed_medium | 4 | 28413 | 717.11 (708.50-718.99) | 498.77 | 438.01 | 3 | 0 | 0.925 |
| mixed_medium | 4 | 74921 | 657.21 (652.42-657.90) | 448.52 | 392.82 | 3 | 0 | 0.969 |
| mixed_small | 4 | 28413 | 333.70 (331.02-334.28) | 216.57 | 186.99 | 3 | 0 | 1.147 |
| mixed_small | 4 | 74921 | 374.81 (373.44-377.08) | 263.22 | 233.54 | 3 | 0 | 1.167 |

## 1024/1024

| Case | Scale | Seed | CPU ms (min-max) | Peak MiB | Additional retained MiB | Samples | Failures | CPU ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed_medium | 4 | 28413 | 559.17 (557.16-567.23) | 626.00 | 565.38 | 3 | 0 | 0.721 |
| mixed_medium | 4 | 74921 | 540.19 (536.98-543.81) | 614.87 | 559.16 | 3 | 0 | 0.797 |
| mixed_small | 4 | 28413 | 349.23 (348.10-350.36) | 232.20 | 202.50 | 3 | 0 | 1.201 |
| mixed_small | 4 | 74921 | 381.47 (380.30-384.24) | 278.02 | 248.28 | 3 | 0 | 1.188 |

## 256/4096

| Case | Scale | Seed | CPU ms (min-max) | Peak MiB | Additional retained MiB | Samples | Failures | CPU ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed_medium | 4 | 28413 | 1228.78 (1224.00-1230.36) | 682.22 | 621.59 | 3 | 0 | 1.585 |
| mixed_medium | 4 | 74921 | 1112.68 (1110.61-1118.22) | 580.52 | 524.86 | 3 | 0 | 1.641 |
| mixed_small | 4 | 28413 | 287.71 (286.55-288.90) | 157.31 | 127.79 | 3 | 0 | 0.989 |
| mixed_small | 4 | 74921 | 320.40 (318.90-320.45) | 188.90 | 159.16 | 3 | 0 | 0.998 |

## 1024/4096

| Case | Scale | Seed | CPU ms (min-max) | Peak MiB | Additional retained MiB | Samples | Failures | CPU ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed_medium | 4 | 28413 | 682.53 (673.32-695.24) | 661.26 | 600.63 | 3 | 0 | 0.881 |
| mixed_medium | 4 | 74921 | 649.84 (646.67-653.89) | 669.63 | 613.92 | 3 | 0 | 0.958 |
| mixed_small | 4 | 28413 | 349.53 (347.23-349.98) | 232.14 | 202.50 | 3 | 0 | 1.202 |
| mixed_small | 4 | 74921 | 383.44 (381.21-384.65) | 277.90 | 248.28 | 3 | 0 | 1.194 |
