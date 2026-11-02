### The programs, fixed until they compile

| program | operations | boolean | boolean statements | executions of user operations | copies | operations before fixing | rounds, median / most | fixing | memory | fixes | statuses |
| ------- | ---------- | ------- | ------------------ | ----------------------------- | ------ | ------------------------ | --------------------- | ------ | ------ | ----- | -------- |
| ops_15k | 14,770 | 11,770 | 150,507 | 18,281 | 7,066 | 15,006 | 2 / 17 | 15.5 s | 165 MB | constant 199, dead 158, match 33,449, opposite match 7,673, opposite value 474, redundant 5,496, spelling 11,547, unused view 190, wrapper 111 | ok 15,006 |
| ops_150k | 147,685 | 117,685 | 1,519,207 | 186,564 | 70,248 | 150,006 | 2 / 21 | 159 s | 1.59 GB | constant 2,227, dead 2,129, literal 2, match 335,647, opposite match 76,498, opposite value 4,748, redundant 56,932, spelling 119,472, unused view 1,774, wrapper 1,140 | ok 150,006 |
| ops_2k_wide | 1,978 | 1,578 | 81,781 | 11,454 | 3,101 | 2,006 | 7 / 42 | 54.9 s | 428 MB | constant 22, dead 3, match 4,799, opposite match 625, opposite value 16, redundant 1,033, spelling 12,406, unused view 28, wrapper 7 | ok 2,006 |

### Checking every operation

| program | run | wall | structure | tables | groups | order | redundant | matches | spellings | per operation, median | 99th percentile | slowest | truth tables / SAT | memory | operations with errors |
| ------- | --- | ---- | --------- | ------ | ------ | ----- | --------- | ------- | --------- | --------------------- | --------------- | ------- | ------------------ | ------ | ---------------------- |
| ops_15k | first | 1.85 s | 48.2 ms | 61.6 ms | 3.18 ms | 35.1 ms | 17 ms | 855 ms | 565 ms | 84 µs | 394 µs | 701 µs | 14,770 / 0 | 82.1 MB | 0 |
| ops_150k | first | 18.6 s | 479 ms | 733 ms | 31.8 ms | 360 ms | 176 ms | 8.53 s | 5.65 s | 83.6 µs | 396 µs | 8.18 ms | 147,685 / 0 | 782 MB | 0 |
| ops_2k_wide | first | 19.9 s | 45.8 ms | 13.1 s | 99.2 ms | 56.4 ms | 1.56 s | 2.7 s | 2.2 s | 4.98 ms | 66.1 ms | 106 ms | 1,978 / 0 | 229 MB | 0 |

### Checking again

| program | change | time | operations checked | slowest edit | most checked |
| ------- | ------ | ---- | ------------------ | ------------ | ------------ |
| ops_15k | unchanged, by hashes | 24.9 ms | 0 |  |  |
| ops_15k | 200 random edits | 116 µs median | 1 median | 3.79 ms | 22 |
| ops_15k | booleans.defcl: swap or implies | 579 ms | 14,770 |  | 448 with errors |
| ops_15k | booleans.defcl: register b0_797 | 2.12 s | 14,770 |  | 1,917 with errors |
| ops_150k | unchanged, by hashes | 264 ms | 0 |  |  |
| ops_150k | 200 random edits | 115 µs median | 1 median | 3.33 ms | 16 |
| ops_150k | booleans.defcl: swap or implies | 5.9 s | 147,685 |  | 4,499 with errors |
| ops_150k | booleans.defcl: register b0_7743 | 11 s | 147,685 |  | 17,580 with errors |
| ops_2k_wide | unchanged, by hashes | 14.7 ms | 0 |  |  |
| ops_2k_wide | 200 random edits | 7.12 ms median | 1 median | 2.24 s | 138 |
| ops_2k_wide | booleans.defcl: swap or implies | 16.7 s | 1,978 |  | 196 with errors |

### Time per operation by boolean inputs (first check)

| program | inputs | operations | mean | slowest |
| ------- | ------ | ---------- | ---- | ------- |
| ops_15k | 1 | 87 | 17 µs | 22.1 µs |
| ops_15k | 2 | 257 | 38.3 µs | 103 µs |
| ops_15k | 3 | 2,344 | 39.5 µs | 129 µs |
| ops_15k | 4 | 2,518 | 69.4 µs | 304 µs |
| ops_15k | 5 | 2,544 | 99 µs | 430 µs |
| ops_15k | 6 | 2,529 | 123 µs | 511 µs |
| ops_15k | 7 | 2,225 | 152 µs | 546 µs |
| ops_15k | 8 | 2,210 | 180 µs | 701 µs |
| ops_15k | 9 | 48 | 90.5 µs | 254 µs |
| ops_15k | 10 | 8 | 89 µs | 140 µs |
| ops_150k | 1 | 1,025 | 16.4 µs | 34.6 µs |
| ops_150k | 2 | 2,580 | 37.5 µs | 130 µs |
| ops_150k | 3 | 23,045 | 38.9 µs | 1.75 ms |
| ops_150k | 4 | 25,180 | 69 µs | 671 µs |
| ops_150k | 5 | 25,764 | 98.5 µs | 4.34 ms |
| ops_150k | 6 | 24,623 | 126 µs | 3.82 ms |
| ops_150k | 7 | 23,087 | 153 µs | 3.7 ms |
| ops_150k | 8 | 21,792 | 183 µs | 8.18 ms |
| ops_150k | 9 | 508 | 97 µs | 721 µs |
| ops_150k | 10 | 81 | 106 µs | 245 µs |
| ops_2k_wide | 2 | 4 | 35 µs | 56.6 µs |
| ops_2k_wide | 3 | 2 | 34.9 µs | 35.2 µs |
| ops_2k_wide | 10 | 10 | 356 µs | 648 µs |
| ops_2k_wide | 11 | 20 | 377 µs | 844 µs |
| ops_2k_wide | 12 | 39 | 370 µs | 765 µs |
| ops_2k_wide | 13 | 49 | 502 µs | 1.08 ms |
| ops_2k_wide | 14 | 50 | 622 µs | 1.44 ms |
| ops_2k_wide | 15 | 52 | 1.13 ms | 2.63 ms |
| ops_2k_wide | 16 | 374 | 2.52 ms | 7.24 ms |
| ops_2k_wide | 17 | 386 | 4.28 ms | 14.4 ms |
| ops_2k_wide | 18 | 349 | 8.09 ms | 26.6 ms |
| ops_2k_wide | 19 | 325 | 15.5 ms | 49.5 ms |
| ops_2k_wide | 20 | 318 | 28.9 ms | 106 ms |

### The slowest operations (first check)

| program | operation | inputs | statements | redundant values by | total | checks taking 10% or more | match search nodes |
| ------- | --------- | ------ | ---------- | ------------------- | ----- | ------------------------- | ------------------ |
| ops_15k | b5_150 | 8 | 35 | tt | 701 µs | matches 537 µs, spellings 130 µs | 5,434 |
| ops_15k | b4_448 | 8 | 38 | tt | 625 µs | matches 374 µs, spellings 195 µs | 3,606 |
| ops_15k | b3_528 | 8 | 37 | tt | 608 µs | matches 368 µs, spellings 190 µs | 3,692 |
| ops_15k | b4_347 | 8 | 36 | tt | 596 µs | matches 336 µs, spellings 224 µs | 3,123 |
| ops_15k | b8_423 | 8 | 31 | tt | 579 µs | matches 351 µs, spellings 171 µs | 3,124 |
| ops_150k | m6_1620 | 8 | 2 | tt | 8.18 ms | tables 8.14 ms | 0 |
| ops_150k | b3_5226 | 5 | 6 | tt | 4.34 ms | tables 4.27 ms | 231 |
| ops_150k | b5_6448 | 8 | 30 | tt | 4.19 ms | spellings 3.93 ms | 2,243 |
| ops_150k | b1_7325 | 6 | 15 | tt | 3.82 ms | spellings 3.72 ms | 737 |
| ops_150k | m0_1105 | 7 | 17 | tt | 3.7 ms | matches 3.62 ms | 741 |
| ops_2k_wide | b4_307 | 20 | 75 | tt | 106 ms | tables 90.9 ms | 5,304 |
| ops_2k_wide | b4_285 | 20 | 68 | tt | 98.6 ms | tables 86.9 ms | 3,431 |
| ops_2k_wide | b4_28 | 20 | 70 | tt | 91 ms | tables 77.6 ms | 10,327 |
| ops_2k_wide | b3_313 | 20 | 69 | tt | 90.3 ms | tables 55.4 ms, spellings 26.1 ms | 6,829 |
| ops_2k_wide | b4_300 | 20 | 56 | tt | 81.1 ms | tables 71.1 ms | 4,710 |

ops_15k: the independent checker checked 1,200 operations (300 sampled and what they execute) in 53.4 s; 0 fail it, 0 fail `beq`.

ops_150k: the independent checker checked 1,200 operations (300 sampled and what they execute) in 55.5 s; 0 fail it, 0 fail `beq`.
