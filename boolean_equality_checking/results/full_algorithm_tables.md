### The programs, fixed until they compile

| program | operations | boolean | boolean statements | executions of user operations | copies | operations before fixing | rounds, median / most | fixing | memory | fixes | statuses |
| ------- | ---------- | ------- | ------------------ | ----------------------------- | ------ | ------------------------ | --------------------- | ------ | ------ | ----- | -------- |
| ops_15k | 14,897 | 11,897 | 153,130 | 18,892 | 7,209 | 15,006 | 2 / 17 | 16.4 s | 168 MB | dead 94, match 33,793, opposite match 7,616, opposite value 455, redundant 5,634, spelling 12,049, unused view 66, wrapper 109 | ok 15,006 |
| ops_150k | 148,858 | 118,858 | 1,529,990 | 188,677 | 70,388 | 150,006 | 2 / 21 | 164 s | 1.6 GB | dead 1,236, match 339,427, opposite match 76,839, opposite value 4,497, redundant 54,999, spelling 120,561, unused view 588, wrapper 1,148 | ok 150,006 |
| ops_2k_wide | 1,995 | 1,595 | 81,363 | 11,393 | 3,186 | 2,006 | 7 / 43 | 55.7 s | 417 MB | dead 12, match 4,926, opposite match 605, opposite value 15, redundant 1,084, spelling 12,415, unused view 11, wrapper 11 | ok 2,006 |

### Checking every operation

| program | run | wall | structure | tables | groups | order | redundant | matches | spellings | per operation, median | 99th percentile | slowest | truth tables / SAT | memory | operations with errors |
| ------- | --- | ---- | --------- | ------ | ------ | ----- | --------- | ------- | --------- | --------------------- | --------------- | ------- | ------------------ | ------ | ---------------------- |
| ops_15k | first | 1.89 s | 50.6 ms | 61.5 ms | 3.27 ms | 36.1 ms | 17.5 ms | 877 ms | 572 ms | 84.5 µs | 402 µs | 762 µs | 14,897 / 0 | 83 MB | 0 |
| ops_150k | first | 18.1 s | 471 ms | 717 ms | 31.6 ms | 351 ms | 165 ms | 8.37 s | 5.44 s | 80.8 µs | 380 µs | 8.42 ms | 148,858 / 0 | 787 MB | 0 |
| ops_2k_wide | first | 19.6 s | 47 ms | 13 s | 102 ms | 54.3 ms | 1.5 s | 2.6 s | 2.18 s | 4.57 ms | 72.8 ms | 98.2 ms | 1,995 / 0 | 223 MB | 0 |

### Checking again

| program | change | time | operations checked | slowest edit | most checked |
| ------- | ------ | ---- | ------------------ | ------------ | ------------ |
| ops_15k | unchanged, by hashes | 27.1 ms | 0 |  |  |
| ops_15k | 200 random edits | 118 µs median | 1 median | 2.15 ms | 16 |
| ops_15k | booleans.defcl: register b0_21 | 1.25 s | 14,897 |  | 4,205 with errors |
| ops_150k | unchanged, by hashes | 274 ms | 0 |  |  |
| ops_150k | 200 random edits | 109 µs median | 1 median | 3.58 ms | 33 |
| ops_150k | booleans.defcl: register b0_5919 | 10.3 s | 148,858 |  | 17,505 with errors |
| ops_2k_wide | unchanged, by hashes | 14.2 ms | 0 |  |  |
| ops_2k_wide | 100 random edits | 8.82 ms median | 1 median | 1.34 s | 80 |

### Time per operation by boolean inputs (first check)

| program | inputs | operations | mean | slowest |
| ------- | ------ | ---------- | ---- | ------- |
| ops_15k | 1 | 124 | 16.9 µs | 23.6 µs |
| ops_15k | 2 | 268 | 37.8 µs | 71.3 µs |
| ops_15k | 3 | 2,309 | 40.1 µs | 146 µs |
| ops_15k | 4 | 2,512 | 69.3 µs | 347 µs |
| ops_15k | 5 | 2,571 | 99.1 µs | 431 µs |
| ops_15k | 6 | 2,440 | 127 µs | 588 µs |
| ops_15k | 7 | 2,368 | 152 µs | 762 µs |
| ops_15k | 8 | 2,231 | 183 µs | 628 µs |
| ops_15k | 9 | 63 | 91.8 µs | 244 µs |
| ops_15k | 10 | 11 | 114 µs | 237 µs |
| ops_150k | 1 | 1,030 | 16 µs | 22.2 µs |
| ops_150k | 2 | 2,465 | 35.9 µs | 96.1 µs |
| ops_150k | 3 | 23,224 | 37.7 µs | 3.31 ms |
| ops_150k | 4 | 25,257 | 66.5 µs | 387 µs |
| ops_150k | 5 | 25,701 | 96.1 µs | 8.42 ms |
| ops_150k | 6 | 25,171 | 122 µs | 1.9 ms |
| ops_150k | 7 | 23,455 | 147 µs | 3.22 ms |
| ops_150k | 8 | 21,920 | 175 µs | 3.65 ms |
| ops_150k | 9 | 540 | 87.8 µs | 280 µs |
| ops_150k | 10 | 95 | 105 µs | 239 µs |
| ops_2k_wide | 2 | 4 | 31.6 µs | 50.8 µs |
| ops_2k_wide | 3 | 2 | 32.2 µs | 33.7 µs |
| ops_2k_wide | 10 | 7 | 207 µs | 374 µs |
| ops_2k_wide | 11 | 12 | 283 µs | 518 µs |
| ops_2k_wide | 12 | 44 | 328 µs | 998 µs |
| ops_2k_wide | 13 | 40 | 445 µs | 1.01 ms |
| ops_2k_wide | 14 | 53 | 601 µs | 1.74 ms |
| ops_2k_wide | 15 | 52 | 983 µs | 2.67 ms |
| ops_2k_wide | 16 | 401 | 2.41 ms | 6.94 ms |
| ops_2k_wide | 17 | 382 | 4.05 ms | 11.8 ms |
| ops_2k_wide | 18 | 361 | 7.26 ms | 23 ms |
| ops_2k_wide | 19 | 308 | 13.9 ms | 57.2 ms |
| ops_2k_wide | 20 | 329 | 30.3 ms | 98.2 ms |

### The slowest operations (first check)

| program | operation | inputs | statements | redundant values by | total | checks taking 10% or more | match search nodes |
| ------- | --------- | ------ | ---------- | ------------------- | ----- | ------------------------- | ------------------ |
| ops_15k | b6_620 | 7 | 39 | tt | 762 µs | matches 481 µs, spellings 247 µs | 4,318 |
| ops_15k | b5_928 | 8 | 32 | tt | 628 µs | matches 407 µs, spellings 186 µs | 3,596 |
| ops_15k | b6_531 | 7 | 33 | tt | 615 µs | matches 412 µs, spellings 172 µs | 3,982 |
| ops_15k | b5_580 | 8 | 33 | tt | 608 µs | matches 331 µs, spellings 238 µs | 3,175 |
| ops_15k | b9_880 | 7 | 32 | tt | 608 µs | matches 409 µs, spellings 164 µs | 4,240 |
| ops_150k | m6_885 | 5 | 11 | tt | 8.42 ms | tables 8.32 ms | 370 |
| ops_150k | b3_4876 | 8 | 7 | tt | 3.65 ms | tables 3.58 ms | 255 |
| ops_150k | b5_8574 | 8 | 21 | tt | 3.46 ms | matches 3.35 ms | 1,109 |
| ops_150k | b9_3719 | 3 | 2 | tt | 3.31 ms | matches 3.29 ms | 34 |
| ops_150k | b2_1951 | 7 | 28 | tt | 3.22 ms | spellings 2.98 ms | 1,786 |
| ops_2k_wide | b4_245 | 20 | 65 | tt | 98.2 ms | tables 86 ms | 1,827 |
| ops_2k_wide | b3_183 | 20 | 78 | tt | 94.6 ms | tables 80.9 ms | 1,207 |
| ops_2k_wide | b4_285 | 20 | 54 | tt | 89.9 ms | tables 81.3 ms | 2,036 |
| ops_2k_wide | b2_213 | 20 | 79 | tt | 89.6 ms | tables 76.7 ms | 1,495 |
| ops_2k_wide | b4_9 | 20 | 69 | tt | 87.5 ms | tables 76.4 ms | 4,403 |

ops_15k: the independent checker checked 1,200 operations (300 sampled and what they execute) in 57.2 s; 0 fail it, 0 fail `beq`.

ops_150k: the independent checker checked 1,200 operations (300 sampled and what they execute) in 51.9 s; 0 fail it, 0 fail `beq`.
