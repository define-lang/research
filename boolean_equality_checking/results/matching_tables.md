### Time (median per operation) and values flagged (not planted, per operation)

| size | cuts | cuts_negated | cut_values | exact_cone | exact_support | exact_any |
| ---- | ---- | ------------ | ---------- | ---------- | ------------- | --------- |
| 8 inputs, 64 statements | 501 µs, 2.2 of 74 | 897 µs, 2.4 of 74 | 2.79 ms, 48.2 of 74 | 20.1 ms, 17.6 of 74 | 43 ms, 31.4 of 74 | 47.3 ms, 34.6 of 74 |
| 12 inputs, 64 statements | 463 µs, 1.6 of 73 | 938 µs, 1.6 of 73 | 2.72 ms, 42.8 of 73 | 15.3 ms, 11.8 of 73 | 26.2 ms, 23.2 of 73 | 40.3 ms, 25.6 of 73 |
| 12 inputs, 200 statements | 1.72 ms, 6.8 of 220 | 2.29 ms, 7.6 of 220 | 9.79 ms, 130.8 of 220 | 357 ms, 40.4 of 220 | 577 ms, 77.8 of 220 | 753 ms, 81.8 of 220 |
| 16 inputs, 256 statements | 2.26 ms, 9.0 of 282 | 3.97 ms, 9.8 of 282 | 15.3 ms, 172.4 of 282 | 876 ms, 47.8 of 282 | 1.1 s, 91.4 of 282 | 1.73 s, 96.4 of 282 |
| 20 inputs, 256 statements | 2.74 ms, 9.8 of 283 | 4.83 ms, 10.0 of 283 | 21.6 ms, 171.2 of 283 | 5.87 s, 44.2 of 283 | 1.96 s, 93.6 of 283 | 2.53 s, 97.8 of 283 |

### Planted matches found

| method | local | sop |
| ------ | ----- | --- |
| cuts | 156/162 | 0/11 |
| cuts_negated | 162/162 | 0/11 |
| cut_values | 162/162 | 4/11 |
| exact_cone | 155/162 | 0/11 |
| exact_support | 162/162 | 8/11 |
| exact_any | 162/162 | 9/11 |

### Cost against the arity limit (200- and 256-statement operations)

| arity limit | cuts | exact (cone) |
| ----------- | ---- | ------------ |
| 4 | median 2.15 ms, slowest 3.16 ms, 2,138 cuts | median 298 s, slowest 421 s |
| 5 | median 15.2 ms, slowest 27.8 ms, 4,480 cuts | timeout |
| 6 | median 170 ms, slowest 530 ms, 9,874 cuts | not run |
