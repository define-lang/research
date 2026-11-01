### Flat value operations, combined algorithm (median / slowest of 5)

| inputs | statements | operations | median | slowest | SAT calls | counterexamples | truth tables, median |
| ------ | ---------- | ---------- | ------ | ------- | --------- | --------------- | -------------------- |
| 12 | 64 | compiles | 32.9 µs | 35.7 µs | 0 | 0 | 32.5 µs |
| 12 | 64 | fails | 38.5 µs | 64.9 µs | 0 | 0 | 37.6 µs |
| 12 | 64 | near_c10 | 41 µs | 44.8 µs | 0 | 0 | 41 µs |
| 12 | 256 | compiles | 131 µs | 135 µs | 0 | 0 | 130 µs |
| 12 | 256 | fails | 129 µs | 173 µs | 0 | 0 | 129 µs |
| 12 | 256 | near_c10 | 155 µs | 168 µs | 0 | 0 | 160 µs |
| 16 | 64 | compiles | 38.4 µs | 39.3 µs | 6 | 0 | 429 µs |
| 16 | 64 | fails | 33.8 µs | 43.8 µs | 4 | 0 | 433 µs |
| 16 | 64 | near_c10 | 43.9 µs | 47.1 µs | 10 | 0 | 490 µs |
| 16 | 64 | near_c14 | 80.4 µs | 121 µs | 25 | 9 | 573 µs |
| 16 | 256 | compiles | 193 µs | 294 µs | 58 | 1 | 1.48 ms |
| 16 | 256 | fails | 268 µs | 604 µs | 74 | 0 | 1.71 ms |
| 16 | 256 | near_c10 | 306 µs | 340 µs | 76 | 5 | 1.8 ms |
| 16 | 256 | near_c14 | 779 µs | 922 µs | 114 | 29 | 2.03 ms |
| 20 | 64 | compiles | 34.6 µs | 39.1 µs | 8 | 0 | 7.52 ms |
| 20 | 64 | fails | 37.1 µs | 50 µs | 6 | 0 | 9.78 ms |
| 20 | 64 | near_c10 | 36.5 µs | 43.7 µs | 4 | 0 | 8.39 ms |
| 20 | 64 | near_c14 | 56.4 µs | 143 µs | 21 | 4 | 8.7 ms |
| 20 | 64 | near_c18 | 87.8 µs | 158 µs | 27 | 13 | 8.66 ms |
| 20 | 256 | compiles | 207 µs | 213 µs | 64 | 0 | 30.7 ms |
| 20 | 256 | fails | 267 µs | 1.18 ms | 62 | 0 | 30.7 ms |
| 20 | 256 | near_c10 | 262 µs | 351 µs | 76 | 4 | 32.2 ms |
| 20 | 256 | near_c14 | 814 µs | 989 µs | 119 | 38 | 36 ms |
| 20 | 256 | near_c18 | 1.21 ms | 1.61 ms | 197 | 74 | 33 ms |

### Libraries with references (SAT with the hybrid refinement)

| library | run | operations | total time | SAT calls | patterns stored | most in one operation | operations with a redundant value | operations edited |
| ------- | --- | ---------- | ---------- | --------- | --------------- | --------------------- | --------------------------------- | ----------------- |
| compiles_v10 | edited_without_patterns | 80 | 4.07 ms | 253 | 58 | 3 | 5 | 23 |
| compiles_v10 | first | 80 | 4.01 ms | 227 | 57 | 3 | 0 |  |
| compiles_v10 | recheck_edited | 80 | 3.09 ms | 42 | 3 | 1 | 5 | 23 |
| compiles_v10 | recheck_unchanged | 80 | 2.82 ms | 0 | 0 | 0 | 0 |  |
| compiles_v10 | stop_first | 80 | 3.97 ms | 227 | 57 | 3 | 0 |  |
| compiles_v10 | tt | 80 | 696 µs | 0 | 0 | 0 | 0 |  |
| compiles_v14 | edited_without_patterns | 73 | 28.5 ms | 1297 | 486 | 15 | 3 | 20 |
| compiles_v14 | first | 73 | 29.5 ms | 1330 | 496 | 14 | 0 |  |
| compiles_v14 | recheck_edited | 73 | 16.6 ms | 112 | 34 | 4 | 3 | 20 |
| compiles_v14 | recheck_unchanged | 73 | 16 ms | 0 | 0 | 0 | 0 |  |
| compiles_v14 | stop_first | 73 | 30 ms | 1330 | 496 | 14 | 0 |  |
| compiles_v14 | tt | 73 | 13 ms | 0 | 0 | 0 | 0 |  |
| fails_v10 | edited_without_patterns | 80 | 8.29 ms | 505 | 58 | 3 | 26 | 23 |
| fails_v10 | first | 80 | 10.7 ms | 588 | 57 | 3 | 29 |  |
| fails_v10 | recheck_edited | 80 | 6.62 ms | 347 | 3 | 1 | 26 | 23 |
| fails_v10 | recheck_unchanged | 80 | 7.91 ms | 427 | 0 | 0 | 29 |  |
| fails_v10 | stop_first | 80 | 6.76 ms | 419 | 23 | 3 | 29 |  |
| fails_v10 | tt | 80 | 854 µs | 0 | 0 | 0 | 29 |  |
| fails_v14 | edited_without_patterns | 73 | 36.9 ms | 1458 | 488 | 15 | 29 | 20 |
| fails_v14 | first | 73 | 40.6 ms | 1557 | 496 | 14 | 32 |  |
| fails_v14 | recheck_edited | 73 | 23.2 ms | 390 | 36 | 4 | 29 | 20 |
| fails_v14 | recheck_unchanged | 73 | 24 ms | 394 | 0 | 0 | 32 |  |
| fails_v14 | stop_first | 73 | 26.3 ms | 821 | 230 | 14 | 32 |  |
| fails_v14 | tt | 73 | 16.5 ms | 0 | 0 | 0 | 32 |  |

### Rechecking after one edit

| library | edit | operations | rechecked: median | 90th percentile | most | mean | time: median | slowest |
| ------- | ---- | ---------- | ----------------- | --------------- | ---- | ---- | ------------ | ------- |
| deep_e3_l10 | keeps the function | 91 | 1 | 1 | 1 | 1.00 | 12.3 µs | 20.8 µs |
| deep_e3_l10 | changes it | 91 | 1 | 3 | 10 | 1.60 | 13.7 µs | 150 µs |
| deep_e3_l14 | keeps the function | 113 | 1 | 1 | 1 | 1.00 | 13 µs | 21.3 µs |
| deep_e3_l14 | changes it | 113 | 1 | 3 | 8 | 1.62 | 13.4 µs | 105 µs |
| deep_e4_l12 | keeps the function | 106 | 1 | 1 | 1 | 1.00 | 15.8 µs | 27.2 µs |
| deep_e4_l12 | changes it | 106 | 1 | 4 | 14 | 1.90 | 19.9 µs | 257 µs |
