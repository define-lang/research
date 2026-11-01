### Random programs of 256 statements, fixed until they compile

| inputs | rules | status | rounds | redundant-value fixes | match fixes | statements after | slowest check | check of the result |
| ------ | ----- | ------ | ------ | --------------------- | ----------- | ---------------- | ------------- | ------------------- |
| 12 | largest | ok | 55 | 8 | 47 | 109 | 59 ms | 3.34 ms |
| 12 | largest | ok | 63 | 10 | 53 | 86 | 71.1 ms | 1.89 ms |
| 12 | largest | ok | 59 | 8 | 51 | 106 | 74.3 ms | 2.58 ms |
| 12 | largest | ok | 70 | 12 | 58 | 70 | 68.3 ms | 1.15 ms |
| 12 | largest | ok | 34 | 3 | 31 | 140 | 50.6 ms | 5.79 ms |
| 16 | largest | ok | 49 | 4 | 45 | 98 | 65.3 ms | 2.13 ms |
| 16 | largest | ok | 38 | 2 | 36 | 131 | 65.4 ms | 5.33 ms |
| 16 | largest | ok | 61 | 9 | 52 | 99 | 72.7 ms | 3.46 ms |
| 16 | largest | ok | 44 | 4 | 40 | 112 | 54.6 ms | 3.33 ms |
| 16 | largest | ok | 35 | 2 | 33 | 132 | 42.4 ms | 4.4 ms |
| 20 | largest | ok | 56 | 9 | 47 | 111 | 443 ms | 12.7 ms |
| 20 | largest | ok | 45 | 5 | 40 | 128 | 152 ms | 15.5 ms |
| 20 | largest | ok | 29 | 0 | 29 | 142 | 66.2 ms | 18.2 ms |
| 20 | largest | ok | 48 | 4 | 44 | 70 | 422 ms | 8.67 ms |
| 20 | largest | ok | 51 | 9 | 42 | 110 | 426 ms | 15.2 ms |
| 12 | largest|prec:A|strict | ok | 68 | 6 | 44 | 103 | 67.4 ms | 4.55 ms |
| 12 | largest|prec:A|strict | ok | 47 | 9 | 30 | 83 | 106 ms | 1.86 ms |
| 12 | largest|prec:A|strict | ok | 62 | 5 | 49 | 96 | 111 ms | 4.03 ms |
| 12 | largest|prec:A|strict | ok | 61 | 10 | 44 | 65 | 102 ms | 1.59 ms |
| 12 | largest|prec:A|strict | ok | 56 | 3 | 26 | 139 | 67.3 ms | 9.54 ms |
| 16 | largest|prec:A|strict | ok | 61 | 4 | 44 | 94 | 88.2 ms | 3.49 ms |
| 16 | largest|prec:A|strict | ok | 51 | 2 | 36 | 129 | 93.4 ms | 8.04 ms |
| 16 | largest|prec:A|strict | ok | 61 | 8 | 39 | 100 | 124 ms | 5.47 ms |
| 16 | largest|prec:A|strict | ok | 67 | 3 | 44 | 115 | 86 ms | 5.99 ms |
| 16 | largest|prec:A|strict | ok | 56 | 2 | 31 | 123 | 61.6 ms | 6.97 ms |
| 20 | largest|prec:A|strict | ok | 59 | 8 | 35 | 119 | 702 ms | 18.2 ms |
| 20 | largest|prec:A|strict | ok | 46 | 4 | 32 | 128 | 224 ms | 19.1 ms |
| 20 | largest|prec:A|strict | ok | 44 | 0 | 27 | 143 | 94.1 ms | 23.2 ms |
| 20 | largest|prec:A|strict | ok | 43 | 2 | 34 | 63 | 569 ms | 8.56 ms |
| 20 | largest|prec:A|strict | ok | 78 | 7 | 50 | 111 | 574 ms | 21 ms |
| 12 | largest|strict | ok | 47 | 5 | 42 | 108 | 47.4 ms | 2.78 ms |
| 12 | largest|strict | ok | 51 | 10 | 41 | 102 | 71.3 ms | 1.71 ms |
| 12 | largest|strict | ok | 55 | 8 | 47 | 106 | 77.3 ms | 2.64 ms |
| 12 | largest|strict | ok | 62 | 12 | 50 | 72 | 68.2 ms | 1.11 ms |
| 12 | largest|strict | ok | 29 | 3 | 26 | 141 | 49.9 ms | 4.96 ms |
| 16 | largest|strict | ok | 44 | 4 | 40 | 99 | 66.4 ms | 2.17 ms |
| 16 | largest|strict | ok | 32 | 2 | 30 | 134 | 63.8 ms | 6.19 ms |
| 16 | largest|strict | ok | 53 | 8 | 45 | 96 | 72.5 ms | 2.67 ms |
| 16 | largest|strict | ok | 32 | 3 | 29 | 122 | 53.4 ms | 4.04 ms |
| 16 | largest|strict | ok | 30 | 2 | 28 | 135 | 43.2 ms | 5.26 ms |
| 20 | largest|strict | ok | 50 | 9 | 41 | 112 | 449 ms | 13.5 ms |
| 20 | largest|strict | ok | 42 | 5 | 37 | 128 | 156 ms | 15.8 ms |
| 20 | largest|strict | ok | 25 | 0 | 25 | 143 | 67.1 ms | 17.5 ms |
| 20 | largest|strict | ok | 42 | 4 | 38 | 72 | 407 ms | 8.77 ms |
| 20 | largest|strict | ok | 38 | 7 | 31 | 117 | 412 ms | 16 ms |

### Families: does every program reach the same one?

| rewrites | inputs | policy | families that converge | distinct results per family | variants reaching the base's result | rounds, median / most | statuses |
| -------- | ------ | ------ | ---------------------- | --------------------------- | ----------------------------------- | --------------------- | -------- |
| demorgan | 8 | earliest | 1/8 | 2.8 | 14/32 | 4 / 11 | ok 40 |
| demorgan | 8 | earliest|prec:A|strict | 1/8 | 2.6 | 15/32 | 5 / 12 | ok 40 |
| demorgan | 8 | largest | 1/8 | 2.8 | 14/32 | 3 / 9 | ok 40 |
| demorgan | 8 | largest+plain | 0/8 | 2.8 | 13/32 | 4 / 14 | ok 40 |
| demorgan | 8 | largest|prec:A | 1/8 | 2.6 | 15/32 | 4 / 12 | cycle 3, ok 37 |
| demorgan | 8 | largest|prec:A|strict | 1/8 | 2.6 | 15/32 | 4 / 8 | ok 40 |
| demorgan | 8 | largest|prec:B|strict | 1/8 | 2.6 | 15/32 | 4 / 8 | ok 40 |
| demorgan | 8 | largest|strict | 1/8 | 2.8 | 14/32 | 3 / 9 | ok 40 |
| demorgan | 8 | smallest | 1/8 | 2.8 | 14/32 | 5 / 13 | ok 40 |
| demorgan | 8 | smallest|prec:A|strict | 1/8 | 2.6 | 15/32 | 6 / 13 | ok 40 |
| demorgan | 12 | earliest | 0/8 | 4.1 | 4/32 | 8 / 19 | ok 40 |
| demorgan | 12 | earliest|prec:A|strict | 0/8 | 4.0 | 6/32 | 11 / 20 | ok 40 |
| demorgan | 12 | largest | 0/8 | 4.1 | 4/32 | 6 / 16 | ok 40 |
| demorgan | 12 | largest+plain | 0/8 | 4.0 | 5/32 | 10 / 19 | ok 40 |
| demorgan | 12 | largest|prec:A | 0/8 | 3.9 | 6/32 | 10 / 17 | cycle 11, ok 29 |
| demorgan | 12 | largest|prec:A|strict | 0/8 | 4.1 | 4/32 | 8 / 14 | ok 40 |
| demorgan | 12 | largest|prec:B|strict | 0/8 | 4.1 | 4/32 | 8 / 14 | ok 40 |
| demorgan | 12 | largest|strict | 0/8 | 4.1 | 4/32 | 6 / 16 | ok 40 |
| demorgan | 12 | smallest | 0/8 | 4.2 | 3/32 | 10 / 20 | ok 40 |
| demorgan | 12 | smallest|prec:A|strict | 0/8 | 4.2 | 4/32 | 11 / 22 | ok 40 |
| demorgan | 16 | earliest | 0/8 | 4.5 | 3/32 | 16 / 23 | ok 40 |
| demorgan | 16 | earliest|prec:A|strict | 0/8 | 4.6 | 3/32 | 17 / 27 | ok 40 |
| demorgan | 16 | largest | 0/8 | 4.6 | 3/32 | 12 / 21 | ok 40 |
| demorgan | 16 | largest+plain | 0/8 | 4.8 | 2/32 | 17 / 35 | ok 40 |
| demorgan | 16 | largest|prec:A | 0/8 | 4.5 | 3/32 | 16 / 27 | cycle 11, ok 29 |
| demorgan | 16 | largest|prec:A|strict | 0/8 | 4.6 | 3/32 | 12 / 22 | ok 40 |
| demorgan | 16 | largest|prec:B|strict | 0/8 | 4.6 | 3/32 | 12 / 22 | ok 40 |
| demorgan | 16 | largest|strict | 0/8 | 4.6 | 3/32 | 11 / 21 | ok 40 |
| demorgan | 16 | smallest | 0/8 | 4.5 | 3/32 | 17 / 26 | ok 40 |
| demorgan | 16 | smallest|prec:A|strict | 0/8 | 4.8 | 2/32 | 17 / 29 | ok 40 |
| distribute | 8 | earliest | 6/8 | 1.4 | 24/32 | 1 / 6 | ok 40 |
| distribute | 8 | earliest|prec:A|strict | 6/8 | 1.2 | 24/32 | 2 / 5 | ok 40 |
| distribute | 8 | largest | 6/8 | 1.4 | 24/32 | 1 / 6 | ok 40 |
| distribute | 8 | largest|prec:A | 6/8 | 1.2 | 24/32 | 2 / 5 | ok 40 |
| distribute | 8 | largest|prec:A|strict | 6/8 | 1.2 | 24/32 | 2 / 5 | ok 40 |
| distribute | 8 | largest|prec:B|strict | 6/8 | 1.4 | 24/32 | 2 / 5 | ok 40 |
| distribute | 8 | largest|strict | 6/8 | 1.4 | 24/32 | 1 / 4 | ok 40 |
| distribute | 8 | smallest | 6/8 | 1.4 | 24/32 | 1 / 7 | ok 40 |
| distribute | 8 | smallest|prec:A|strict | 6/8 | 1.2 | 24/32 | 2 / 5 | ok 40 |
| distribute | 12 | earliest | 5/8 | 1.5 | 25/32 | 6 / 9 | ok 40 |
| distribute | 12 | earliest|prec:A|strict | 5/8 | 1.4 | 27/32 | 5 / 8 | ok 40 |
| distribute | 12 | largest | 5/8 | 1.6 | 23/32 | 4 / 6 | ok 40 |
| distribute | 12 | largest|prec:A | 5/8 | 1.5 | 25/32 | 6 / 7 | cycle 8, ok 32 |
| distribute | 12 | largest|prec:A|strict | 5/8 | 1.5 | 25/32 | 4 / 7 | ok 40 |
| distribute | 12 | largest|prec:B|strict | 5/8 | 1.5 | 25/32 | 5 / 7 | ok 40 |
| distribute | 12 | largest|strict | 5/8 | 1.6 | 23/32 | 3 / 6 | ok 40 |
| distribute | 12 | smallest | 5/8 | 1.5 | 25/32 | 6 / 10 | ok 40 |
| distribute | 12 | smallest|prec:A|strict | 5/8 | 1.4 | 27/32 | 6 / 11 | ok 40 |
| distribute | 16 | earliest | 1/8 | 2.5 | 11/32 | 6 / 15 | ok 40 |
| distribute | 16 | earliest|prec:A|strict | 2/8 | 2.5 | 13/32 | 6 / 15 | ok 40 |
| distribute | 16 | largest | 2/8 | 2.4 | 12/32 | 5 / 7 | ok 40 |
| distribute | 16 | largest|prec:A | 3/8 | 2.2 | 14/32 | 8 / 16 | cycle 5, ok 35 |
| distribute | 16 | largest|prec:A|strict | 3/8 | 2.4 | 14/32 | 6 / 10 | ok 40 |
| distribute | 16 | largest|prec:B|strict | 3/8 | 2.4 | 14/32 | 7 / 12 | ok 40 |
| distribute | 16 | largest|strict | 2/8 | 2.5 | 12/32 | 4 / 7 | ok 40 |
| distribute | 16 | smallest | 2/8 | 2.4 | 12/32 | 6 / 18 | ok 40 |
| distribute | 16 | smallest|prec:A|strict | 2/8 | 2.5 | 13/32 | 8 / 14 | ok 40 |
| duplicate | 8 | earliest | 8/8 | 1.0 | 32/32 | 2 / 6 | ok 40 |
| duplicate | 8 | earliest|prec:A|strict | 8/8 | 1.0 | 32/32 | 4 / 6 | ok 40 |
| duplicate | 8 | largest | 8/8 | 1.0 | 32/32 | 2 / 4 | ok 40 |
| duplicate | 8 | largest|prec:A | 8/8 | 1.0 | 32/32 | 3 / 7 | cycle 5, ok 35 |
| duplicate | 8 | largest|prec:A|strict | 8/8 | 1.0 | 32/32 | 3 / 5 | ok 40 |
| duplicate | 8 | largest|prec:B|strict | 8/8 | 1.0 | 32/32 | 4 / 5 | ok 40 |
| duplicate | 8 | largest|strict | 8/8 | 1.0 | 32/32 | 2 / 4 | ok 40 |
| duplicate | 8 | smallest | 8/8 | 1.0 | 32/32 | 3 / 10 | ok 40 |
| duplicate | 8 | smallest|prec:A|strict | 8/8 | 1.0 | 32/32 | 4 / 8 | ok 40 |
| duplicate | 12 | earliest | 8/8 | 1.0 | 32/32 | 4 / 9 | ok 40 |
| duplicate | 12 | earliest|prec:A|strict | 8/8 | 1.0 | 32/32 | 6 / 9 | ok 40 |
| duplicate | 12 | largest | 8/8 | 1.0 | 32/32 | 4 / 7 | ok 40 |
| duplicate | 12 | largest|prec:A | 8/8 | 1.0 | 32/32 | 6 / 9 | ok 40 |
| duplicate | 12 | largest|prec:A|strict | 8/8 | 1.0 | 32/32 | 5 / 7 | ok 40 |
| duplicate | 12 | largest|prec:B|strict | 8/8 | 1.0 | 32/32 | 5 / 6 | ok 40 |
| duplicate | 12 | largest|strict | 8/8 | 1.0 | 32/32 | 4 / 5 | ok 40 |
| duplicate | 12 | smallest | 8/8 | 1.0 | 32/32 | 4 / 9 | ok 40 |
| duplicate | 12 | smallest|prec:A|strict | 8/8 | 1.0 | 32/32 | 6 / 9 | ok 40 |
| duplicate | 16 | earliest | 8/8 | 1.0 | 32/32 | 6 / 12 | ok 40 |
| duplicate | 16 | earliest|prec:A|strict | 8/8 | 1.0 | 32/32 | 8 / 12 | ok 40 |
| duplicate | 16 | largest | 8/8 | 1.0 | 32/32 | 6 / 8 | ok 40 |
| duplicate | 16 | largest|prec:A | 8/8 | 1.0 | 32/32 | 8 / 10 | ok 40 |
| duplicate | 16 | largest|prec:A|strict | 8/8 | 1.0 | 32/32 | 6 / 10 | ok 40 |
| duplicate | 16 | largest|prec:B|strict | 8/8 | 1.0 | 32/32 | 8 / 11 | ok 40 |
| duplicate | 16 | largest|strict | 8/8 | 1.0 | 32/32 | 4 / 7 | ok 40 |
| duplicate | 16 | smallest | 8/8 | 1.0 | 32/32 | 7 / 14 | ok 40 |
| duplicate | 16 | smallest|prec:A|strict | 8/8 | 1.0 | 32/32 | 8 / 14 | ok 40 |
| expand | 8 | earliest | 1/8 | 2.6 | 17/32 | 12 / 36 | ok 40 |
| expand | 8 | earliest|prec:A|strict | 4/8 | 2.0 | 23/32 | 11 / 28 | ok 40 |
| expand | 8 | largest | 1/8 | 3.0 | 15/32 | 6 / 22 | ok 40 |
| expand | 8 | largest+plain | 1/8 | 2.8 | 15/32 | 7 / 25 | ok 40 |
| expand | 8 | largest|prec:A | 2/8 | 2.5 | 18/32 | 6 / 22 | cycle 3, ok 37 |
| expand | 8 | largest|prec:A|strict | 1/8 | 2.8 | 17/32 | 6 / 20 | ok 40 |
| expand | 8 | largest|prec:B|strict | 1/8 | 2.8 | 17/32 | 6 / 20 | ok 40 |
| expand | 8 | largest|strict | 1/8 | 3.1 | 15/32 | 6 / 20 | ok 40 |
| expand | 8 | smallest | 2/8 | 2.9 | 16/32 | 16 / 41 | ok 40 |
| expand | 8 | smallest|prec:A|strict | 1/8 | 2.6 | 18/32 | 14 / 34 | ok 40 |
| expand | 12 | earliest | 0/8 | 4.6 | 1/32 | 28 / 54 | ok 40 |
| expand | 12 | earliest|prec:A|strict | 0/8 | 3.0 | 8/32 | 23 / 43 | ok 40 |
| expand | 12 | largest | 0/8 | 4.6 | 2/32 | 16 / 32 | ok 40 |
| expand | 12 | largest+plain | 0/8 | 4.4 | 3/32 | 16 / 42 | ok 40 |
| expand | 12 | largest|prec:A | 2/8 | 3.2 | 13/32 | 18 / 34 | ok 40 |
| expand | 12 | largest|prec:A|strict | 2/8 | 3.4 | 13/32 | 15 / 31 | ok 40 |
| expand | 12 | largest|prec:B|strict | 1/8 | 3.5 | 12/32 | 15 / 32 | ok 40 |
| expand | 12 | largest|strict | 0/8 | 4.9 | 1/32 | 14 / 30 | ok 40 |
| expand | 12 | smallest | 0/8 | 4.6 | 2/32 | 34 / 59 | ok 40 |
| expand | 12 | smallest|prec:A|strict | 0/8 | 4.8 | 2/32 | 30 / 53 | ok 40 |
| expand | 16 | earliest | 0/8 | 5.0 | 0/32 | 48 / 77 | ok 40 |
| expand | 16 | earliest|prec:A|strict | 0/8 | 4.2 | 5/32 | 38 / 59 | ok 40 |
| expand | 16 | largest | 0/8 | 5.0 | 0/32 | 28 / 47 | ok 40 |
| expand | 16 | largest+plain | 0/8 | 4.9 | 1/32 | 33 / 63 | ok 40 |
| expand | 16 | largest|prec:A | 0/8 | 4.6 | 2/32 | 29 / 57 | cycle 21, ok 19 |
| expand | 16 | largest|prec:A|strict | 0/8 | 4.8 | 2/32 | 24 / 41 | ok 40 |
| expand | 16 | largest|prec:B|strict | 0/8 | 4.8 | 2/32 | 25 / 41 | ok 40 |
| expand | 16 | largest|strict | 0/8 | 5.0 | 0/32 | 24 / 39 | ok 40 |
| expand | 16 | smallest | 0/8 | 5.0 | 0/32 | 59 / 90 | ok 40 |
| expand | 16 | smallest|prec:A|strict | 0/8 | 5.0 | 0/32 | 49 / 76 | ok 40 |
| mixed | 8 | earliest | 0/8 | 4.6 | 2/32 | 16 / 31 | ok 40 |
| mixed | 8 | earliest|prec:A|strict | 0/8 | 4.9 | 1/32 | 14 / 27 | ok 40 |
| mixed | 8 | largest | 0/8 | 4.6 | 2/32 | 9 / 22 | ok 40 |
| mixed | 8 | largest+plain | 0/8 | 4.8 | 1/32 | 11 / 23 | ok 40 |
| mixed | 8 | largest|prec:A | 0/8 | 4.1 | 4/32 | 10 / 22 | cycle 8, ok 32 |
| mixed | 8 | largest|prec:A|strict | 0/8 | 4.6 | 2/32 | 8 / 22 | ok 40 |
| mixed | 8 | largest|prec:B|strict | 0/8 | 4.6 | 2/32 | 8 / 22 | ok 40 |
| mixed | 8 | largest|strict | 0/8 | 4.8 | 2/32 | 9 / 21 | ok 40 |
| mixed | 8 | smallest | 0/8 | 4.6 | 2/32 | 19 / 42 | ok 40 |
| mixed | 8 | smallest|prec:A|strict | 0/8 | 4.6 | 1/32 | 17 / 34 | ok 40 |
| mixed | 12 | earliest | 0/8 | 5.0 | 0/32 | 31 / 52 | ok 40 |
| mixed | 12 | earliest|prec:A|strict | 0/8 | 4.9 | 0/32 | 26 / 51 | ok 40 |
| mixed | 12 | largest | 0/8 | 5.0 | 0/32 | 19 / 32 | ok 40 |
| mixed | 12 | largest+plain | 0/8 | 5.0 | 0/32 | 24 / 43 | ok 40 |
| mixed | 12 | largest|prec:A | 0/8 | 5.0 | 0/32 | 20 / 35 | cycle 8, ok 32 |
| mixed | 12 | largest|prec:A|strict | 0/8 | 5.0 | 0/32 | 18 / 31 | ok 40 |
| mixed | 12 | largest|prec:B|strict | 0/8 | 5.0 | 0/32 | 18 / 32 | ok 40 |
| mixed | 12 | largest|strict | 0/8 | 5.0 | 0/32 | 16 / 32 | ok 40 |
| mixed | 12 | smallest | 0/8 | 5.0 | 0/32 | 38 / 59 | ok 40 |
| mixed | 12 | smallest|prec:A|strict | 0/8 | 5.0 | 0/32 | 32 / 59 | ok 40 |
| mixed | 16 | earliest | 0/8 | 5.0 | 0/32 | 50 / 78 | ok 40 |
| mixed | 16 | earliest|prec:A|strict | 0/8 | 5.0 | 0/32 | 41 / 68 | ok 40 |
| mixed | 16 | largest | 0/8 | 5.0 | 0/32 | 32 / 56 | ok 40 |
| mixed | 16 | largest+plain | 0/8 | 5.0 | 0/32 | 42 / 69 | ok 40 |
| mixed | 16 | largest|prec:A | 0/8 | 5.0 | 0/32 | 34 / 55 | cycle 16, ok 24 |
| mixed | 16 | largest|prec:A|strict | 0/8 | 5.0 | 0/32 | 29 / 50 | ok 40 |
| mixed | 16 | largest|prec:B|strict | 0/8 | 5.0 | 0/32 | 29 / 50 | ok 40 |
| mixed | 16 | largest|strict | 0/8 | 5.0 | 0/32 | 28 / 49 | ok 40 |
| mixed | 16 | smallest | 0/8 | 5.0 | 0/32 | 60 / 92 | ok 40 |
| mixed | 16 | smallest|prec:A|strict | 0/8 | 5.0 | 0/32 | 49 / 80 | ok 40 |
| reassociate | 8 | earliest | 6/8 | 1.2 | 28/32 | 2 / 4 | ok 40 |
| reassociate | 8 | earliest|prec:A|strict | 6/8 | 1.2 | 28/32 | 2 / 3 | ok 40 |
| reassociate | 8 | largest | 6/8 | 1.2 | 28/32 | 2 / 4 | ok 40 |
| reassociate | 8 | largest|prec:A | 6/8 | 1.2 | 28/32 | 3 / 5 | cycle 5, ok 35 |
| reassociate | 8 | largest|prec:A|strict | 6/8 | 1.2 | 28/32 | 2 / 5 | ok 40 |
| reassociate | 8 | largest|prec:B|strict | 6/8 | 1.2 | 28/32 | 2 / 5 | ok 40 |
| reassociate | 8 | largest|strict | 6/8 | 1.2 | 28/32 | 1 / 4 | ok 40 |
| reassociate | 8 | smallest | 6/8 | 1.2 | 28/32 | 2 / 4 | ok 40 |
| reassociate | 8 | smallest|prec:A|strict | 6/8 | 1.2 | 28/32 | 2 / 3 | ok 40 |
| reassociate | 12 | earliest | 4/8 | 1.5 | 21/32 | 4 / 8 | ok 40 |
| reassociate | 12 | earliest|prec:A|strict | 3/8 | 1.6 | 18/32 | 5 / 7 | ok 40 |
| reassociate | 12 | largest | 4/8 | 1.5 | 21/32 | 4 / 7 | ok 40 |
| reassociate | 12 | largest|prec:A | 4/8 | 1.5 | 21/32 | 5 / 8 | cycle 5, ok 35 |
| reassociate | 12 | largest|prec:A|strict | 4/8 | 1.5 | 21/32 | 5 / 8 | ok 40 |
| reassociate | 12 | largest|prec:B|strict | 4/8 | 1.5 | 21/32 | 5 / 9 | ok 40 |
| reassociate | 12 | largest|strict | 4/8 | 1.5 | 21/32 | 4 / 7 | ok 40 |
| reassociate | 12 | smallest | 4/8 | 1.5 | 21/32 | 4 / 8 | ok 40 |
| reassociate | 12 | smallest|prec:A|strict | 3/8 | 1.6 | 18/32 | 5 / 7 | ok 40 |
| reassociate | 16 | earliest | 5/8 | 1.4 | 23/32 | 4 / 10 | ok 40 |
| reassociate | 16 | earliest|prec:A|strict | 4/8 | 1.5 | 20/32 | 8 / 12 | ok 40 |
| reassociate | 16 | largest | 5/8 | 1.5 | 22/32 | 4 / 6 | ok 40 |
| reassociate | 16 | largest|prec:A | 5/8 | 1.5 | 22/32 | 8 / 13 | cycle 16, ok 24 |
| reassociate | 16 | largest|prec:A|strict | 4/8 | 1.6 | 19/32 | 8 / 9 | ok 40 |
| reassociate | 16 | largest|prec:B|strict | 4/8 | 1.6 | 19/32 | 7 / 10 | ok 40 |
| reassociate | 16 | largest|strict | 4/8 | 1.6 | 19/32 | 3 / 5 | ok 40 |
| reassociate | 16 | smallest | 4/8 | 1.5 | 22/32 | 4 / 11 | ok 40 |
| reassociate | 16 | smallest|prec:A|strict | 3/8 | 1.6 | 19/32 | 8 / 14 | ok 40 |

### Checking the fixed programs, which compile

| rules | inputs | programs | statements, median | median | slowest |
| ----- | ------ | -------- | ------------------ | ------ | ------- |
| earliest | 8 | 240 | 10 | 37.2 µs | 132 µs |
| earliest | 12 | 240 | 18 | 97.6 µs | 243 µs |
| earliest | 16 | 240 | 33 | 461 µs | 785 µs |
| earliest|prec:A|strict | 8 | 240 | 10 | 52.7 µs | 166 µs |
| earliest|prec:A|strict | 12 | 240 | 18 | 144 µs | 390 µs |
| earliest|prec:A|strict | 16 | 240 | 33 | 607 µs | 1.14 ms |
| largest | 8 | 240 | 10 | 36.7 µs | 95.7 µs |
| largest | 12 | 240 | 18 | 94.9 µs | 250 µs |
| largest | 16 | 240 | 33 | 474 µs | 758 µs |
| largest+plain | 8 | 120 | 11 | 39.8 µs | 86 µs |
| largest+plain | 12 | 120 | 19 | 98.9 µs | 258 µs |
| largest+plain | 16 | 120 | 31 | 450 µs | 661 µs |
| largest|prec:A | 8 | 240 | 10 | 56.1 µs | 161 µs |
| largest|prec:A | 12 | 240 | 18 | 147 µs | 447 µs |
| largest|prec:A | 16 | 240 | 32 | 632 µs | 2.17 ms |
| largest|prec:A|strict | 8 | 240 | 10 | 52.6 µs | 172 µs |
| largest|prec:A|strict | 12 | 240 | 18 | 142 µs | 399 µs |
| largest|prec:A|strict | 16 | 240 | 33 | 609 µs | 1.07 ms |
| largest|prec:B|strict | 8 | 240 | 10 | 51.5 µs | 139 µs |
| largest|prec:B|strict | 12 | 240 | 18 | 138 µs | 354 µs |
| largest|prec:B|strict | 16 | 240 | 33 | 596 µs | 1.02 ms |
| largest|strict | 8 | 240 | 11 | 36.2 µs | 115 µs |
| largest|strict | 12 | 240 | 19 | 98.7 µs | 259 µs |
| largest|strict | 16 | 240 | 33 | 466 µs | 808 µs |
| smallest | 8 | 240 | 10 | 37.9 µs | 123 µs |
| smallest | 12 | 240 | 18 | 97.7 µs | 240 µs |
| smallest | 16 | 240 | 33 | 460 µs | 778 µs |
| smallest|prec:A|strict | 8 | 240 | 11 | 52.8 µs | 212 µs |
| smallest|prec:A|strict | 12 | 240 | 18 | 147 µs | 419 µs |
| smallest|prec:A|strict | 16 | 240 | 33 | 616 µs | 1.28 ms |

### Does the declared order matter?

| rewrites | programs fixed the same way under orders A and B |
| -------- | ------------------------------------------------ |
| demorgan | 83/120 |
| distribute | 88/120 |
| duplicate | 80/120 |
| expand | 77/120 |
| mixed | 82/120 |
| reassociate | 60/120 |
