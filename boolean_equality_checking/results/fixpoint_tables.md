### Random programs of 256 statements, fixed until they compile

| inputs | rules | status | rounds | redundant-value fixes | match fixes | statements after | slowest check | check of the result |
| ------ | ----- | ------ | ------ | --------------------- | ----------- | ---------------- | ------------- | ------------------- |
| 12 | largest | ok | 54 | 4 | 50 | 111 | 67.3 ms | 3.57 ms |
| 12 | largest | ok | 52 | 2 | 50 | 96 | 99.2 ms | 1.4 ms |
| 12 | largest | ok | 55 | 4 | 51 | 106 | 68.8 ms | 3.22 ms |
| 12 | largest | ok | 50 | 3 | 47 | 73 | 104 ms | 1.54 ms |
| 12 | largest | ok | 31 | 0 | 31 | 140 | 48.2 ms | 5.72 ms |
| 16 | largest | ok | 45 | 0 | 45 | 98 | 65.9 ms | 2.19 ms |
| 16 | largest | ok | 38 | 1 | 37 | 130 | 66.9 ms | 5.06 ms |
| 16 | largest | ok | 61 | 2 | 59 | 100 | 78.5 ms | 3.3 ms |
| 16 | largest | ok | 43 | 0 | 43 | 112 | 60.2 ms | 3.55 ms |
| 16 | largest | ok | 35 | 1 | 34 | 132 | 56.9 ms | 4.47 ms |
| 20 | largest | ok | 52 | 1 | 51 | 115 | 837 ms | 12.8 ms |
| 20 | largest | ok | 39 | 3 | 36 | 140 | 248 ms | 17.3 ms |
| 20 | largest | ok | 29 | 0 | 29 | 142 | 64.4 ms | 17.7 ms |
| 20 | largest | ok | 47 | 3 | 44 | 70 | 569 ms | 8.34 ms |
| 20 | largest | ok | 48 | 3 | 45 | 110 | 427 ms | 14.8 ms |
| 12 | largest|strict | ok | 43 | 1 | 42 | 113 | 52.6 ms | 3.52 ms |
| 12 | largest|strict | ok | 46 | 2 | 44 | 98 | 102 ms | 1.69 ms |
| 12 | largest|strict | ok | 53 | 4 | 49 | 103 | 71.4 ms | 2.47 ms |
| 12 | largest|strict | ok | 45 | 2 | 43 | 73 | 103 ms | 1.25 ms |
| 12 | largest|strict | ok | 26 | 0 | 26 | 140 | 51 ms | 5.44 ms |
| 16 | largest|strict | ok | 40 | 0 | 40 | 99 | 66.4 ms | 2.12 ms |
| 16 | largest|strict | ok | 32 | 1 | 31 | 133 | 68 ms | 5.8 ms |
| 16 | largest|strict | ok | 59 | 2 | 57 | 100 | 79.9 ms | 3.05 ms |
| 16 | largest|strict | ok | 35 | 0 | 35 | 119 | 64.5 ms | 3.08 ms |
| 16 | largest|strict | ok | 30 | 1 | 29 | 135 | 53.5 ms | 5.34 ms |
| 20 | largest|strict | ok | 47 | 1 | 46 | 117 | 786 ms | 13.3 ms |
| 20 | largest|strict | ok | 38 | 3 | 35 | 140 | 248 ms | 17.1 ms |
| 20 | largest|strict | ok | 25 | 0 | 25 | 143 | 65.8 ms | 18.6 ms |
| 20 | largest|strict | ok | 41 | 3 | 38 | 72 | 568 ms | 9.2 ms |
| 20 | largest|strict | ok | 35 | 1 | 34 | 117 | 465 ms | 15.9 ms |
| 12 | largest|prec:A|strict | ok | 58 | 0 | 41 | 101 | 70 ms | 4.28 ms |
| 12 | largest|prec:A|strict | ok | 42 | 1 | 30 | 86 | 144 ms | 2.67 ms |
| 12 | largest|prec:A|strict | ok | 68 | 0 | 48 | 109 | 98.8 ms | 5.43 ms |
| 12 | largest|prec:A|strict | ok | 52 | 1 | 43 | 67 | 134 ms | 1.36 ms |
| 12 | largest|prec:A|strict | ok | 64 | 0 | 31 | 134 | 64.5 ms | 7.5 ms |
| 16 | largest|prec:A|strict | ok | 58 | 0 | 44 | 94 | 84.5 ms | 3.26 ms |
| 16 | largest|prec:A|strict | ok | 52 | 2 | 33 | 130 | 90 ms | 7.58 ms |
| 16 | largest|prec:A|strict | ok | 62 | 1 | 47 | 93 | 110 ms | 4.76 ms |
| 16 | largest|prec:A|strict | ok | 54 | 0 | 38 | 112 | 92.5 ms | 4.89 ms |
| 16 | largest|prec:A|strict | ok | 60 | 0 | 33 | 127 | 73.6 ms | 8.14 ms |
| 20 | largest|prec:A|strict | ok | 57 | 0 | 42 | 114 | 973 ms | 17.8 ms |
| 20 | largest|prec:A|strict | ok | 53 | 0 | 36 | 130 | 332 ms | 21.1 ms |
| 20 | largest|prec:A|strict | ok | 44 | 0 | 27 | 143 | 94.2 ms | 23.1 ms |
| 20 | largest|prec:A|strict | ok | 43 | 1 | 34 | 63 | 760 ms | 8.61 ms |
| 20 | largest|prec:A|strict | ok | 69 | 0 | 50 | 111 | 605 ms | 22.8 ms |

### Families: does every program reach the same one?

| rewrites | inputs | policy | families that converge | distinct results per family | variants reaching the base's result | rounds, median / most | statuses |
| -------- | ------ | ------ | ---------------------- | --------------------------- | ----------------------------------- | --------------------- | -------- |
| demorgan | 8 | earliest | 1/8 | 2.6 | 15/32 | 4 / 11 | ok 40 |
| demorgan | 8 | earliest|prec:A|strict | 1/8 | 2.6 | 15/32 | 5 / 12 | ok 40 |
| demorgan | 8 | largest | 1/8 | 2.8 | 14/32 | 3 / 9 | ok 40 |
| demorgan | 8 | largest+plain | 0/8 | 2.8 | 13/32 | 4 / 14 | ok 40 |
| demorgan | 8 | largest|prec:A | 1/8 | 2.6 | 15/32 | 4 / 12 | cycle 1, ok 39 |
| demorgan | 8 | largest|prec:A|strict | 1/8 | 2.6 | 15/32 | 4 / 9 | ok 40 |
| demorgan | 8 | largest|prec:B|strict | 1/8 | 2.6 | 15/32 | 4 / 9 | ok 40 |
| demorgan | 8 | largest|strict | 1/8 | 2.8 | 14/32 | 3 / 9 | ok 40 |
| demorgan | 8 | smallest | 1/8 | 2.6 | 15/32 | 5 / 13 | ok 40 |
| demorgan | 8 | smallest|prec:A|strict | 1/8 | 2.6 | 15/32 | 6 / 13 | ok 40 |
| demorgan | 12 | earliest | 0/8 | 4.1 | 4/32 | 8 / 19 | ok 40 |
| demorgan | 12 | earliest|prec:A|strict | 0/8 | 4.0 | 6/32 | 11 / 23 | ok 40 |
| demorgan | 12 | largest | 0/8 | 4.1 | 4/32 | 6 / 16 | ok 40 |
| demorgan | 12 | largest+plain | 0/8 | 4.0 | 5/32 | 10 / 19 | ok 40 |
| demorgan | 12 | largest|prec:A | 0/8 | 3.8 | 8/32 | 12 / 24 | cycle 6, ok 34 |
| demorgan | 12 | largest|prec:A|strict | 0/8 | 4.1 | 4/32 | 8 / 17 | ok 40 |
| demorgan | 12 | largest|prec:B|strict | 0/8 | 4.1 | 4/32 | 8 / 18 | ok 40 |
| demorgan | 12 | largest|strict | 0/8 | 4.1 | 4/32 | 6 / 16 | ok 40 |
| demorgan | 12 | smallest | 0/8 | 4.2 | 3/32 | 10 / 20 | ok 40 |
| demorgan | 12 | smallest|prec:A|strict | 0/8 | 4.2 | 4/32 | 11 / 25 | ok 40 |
| demorgan | 16 | earliest | 0/8 | 4.5 | 3/32 | 16 / 23 | ok 40 |
| demorgan | 16 | earliest|prec:A|strict | 0/8 | 4.6 | 3/32 | 18 / 27 | ok 40 |
| demorgan | 16 | largest | 0/8 | 4.6 | 3/32 | 12 / 21 | ok 40 |
| demorgan | 16 | largest+plain | 0/8 | 4.8 | 2/32 | 17 / 35 | ok 40 |
| demorgan | 16 | largest|prec:A | 0/8 | 4.5 | 3/32 | 21 / 38 | cycle 4, ok 36 |
| demorgan | 16 | largest|prec:A|strict | 0/8 | 4.6 | 3/32 | 13 / 22 | ok 40 |
| demorgan | 16 | largest|prec:B|strict | 0/8 | 4.6 | 3/32 | 14 / 22 | ok 40 |
| demorgan | 16 | largest|strict | 0/8 | 4.6 | 3/32 | 11 / 21 | ok 40 |
| demorgan | 16 | smallest | 0/8 | 4.5 | 3/32 | 17 / 26 | ok 40 |
| demorgan | 16 | smallest|prec:A|strict | 0/8 | 4.8 | 2/32 | 18 / 29 | ok 40 |
| distribute | 8 | earliest | 6/8 | 1.4 | 24/32 | 1 / 6 | ok 40 |
| distribute | 8 | earliest|prec:A|strict | 6/8 | 1.2 | 24/32 | 2 / 5 | ok 40 |
| distribute | 8 | largest | 6/8 | 1.4 | 24/32 | 1 / 6 | ok 40 |
| distribute | 8 | largest|prec:A | 6/8 | 1.4 | 24/32 | 2 / 8 | ok 40 |
| distribute | 8 | largest|prec:A|strict | 6/8 | 1.2 | 24/32 | 2 / 5 | ok 40 |
| distribute | 8 | largest|prec:B|strict | 6/8 | 1.4 | 24/32 | 2 / 5 | ok 40 |
| distribute | 8 | largest|strict | 6/8 | 1.4 | 24/32 | 1 / 4 | ok 40 |
| distribute | 8 | smallest | 6/8 | 1.4 | 24/32 | 1 / 7 | ok 40 |
| distribute | 8 | smallest|prec:A|strict | 6/8 | 1.2 | 24/32 | 2 / 5 | ok 40 |
| distribute | 12 | earliest | 5/8 | 1.5 | 25/32 | 6 / 8 | ok 40 |
| distribute | 12 | earliest|prec:A|strict | 5/8 | 1.4 | 27/32 | 5 / 8 | ok 40 |
| distribute | 12 | largest | 5/8 | 1.6 | 23/32 | 4 / 6 | ok 40 |
| distribute | 12 | largest|prec:A | 5/8 | 1.5 | 25/32 | 7 / 10 | cycle 3, ok 37 |
| distribute | 12 | largest|prec:A|strict | 5/8 | 1.5 | 25/32 | 4 / 7 | ok 40 |
| distribute | 12 | largest|prec:B|strict | 5/8 | 1.5 | 25/32 | 5 / 7 | ok 40 |
| distribute | 12 | largest|strict | 5/8 | 1.6 | 23/32 | 3 / 6 | ok 40 |
| distribute | 12 | smallest | 5/8 | 1.5 | 25/32 | 6 / 10 | ok 40 |
| distribute | 12 | smallest|prec:A|strict | 5/8 | 1.4 | 27/32 | 6 / 11 | ok 40 |
| distribute | 16 | earliest | 1/8 | 2.5 | 11/32 | 6 / 15 | ok 40 |
| distribute | 16 | earliest|prec:A|strict | 2/8 | 2.5 | 13/32 | 6 / 17 | ok 40 |
| distribute | 16 | largest | 2/8 | 2.4 | 12/32 | 5 / 7 | ok 40 |
| distribute | 16 | largest|prec:A | 3/8 | 2.2 | 14/32 | 9 / 20 | ok 40 |
| distribute | 16 | largest|prec:A|strict | 3/8 | 2.4 | 14/32 | 6 / 11 | ok 40 |
| distribute | 16 | largest|prec:B|strict | 3/8 | 2.4 | 14/32 | 7 / 13 | ok 40 |
| distribute | 16 | largest|strict | 2/8 | 2.5 | 12/32 | 4 / 7 | ok 40 |
| distribute | 16 | smallest | 2/8 | 2.4 | 12/32 | 6 / 18 | ok 40 |
| distribute | 16 | smallest|prec:A|strict | 2/8 | 2.5 | 13/32 | 8 / 17 | ok 40 |
| duplicate | 8 | earliest | 8/8 | 1.0 | 32/32 | 2 / 6 | ok 40 |
| duplicate | 8 | earliest|prec:A|strict | 8/8 | 1.0 | 32/32 | 4 / 6 | ok 40 |
| duplicate | 8 | largest | 8/8 | 1.0 | 32/32 | 2 / 4 | ok 40 |
| duplicate | 8 | largest|prec:A | 8/8 | 1.0 | 32/32 | 4 / 7 | ok 40 |
| duplicate | 8 | largest|prec:A|strict | 8/8 | 1.0 | 32/32 | 3 / 6 | ok 40 |
| duplicate | 8 | largest|prec:B|strict | 8/8 | 1.0 | 32/32 | 4 / 6 | ok 40 |
| duplicate | 8 | largest|strict | 8/8 | 1.0 | 32/32 | 2 / 4 | ok 40 |
| duplicate | 8 | smallest | 8/8 | 1.0 | 32/32 | 3 / 10 | ok 40 |
| duplicate | 8 | smallest|prec:A|strict | 8/8 | 1.0 | 32/32 | 4 / 8 | ok 40 |
| duplicate | 12 | earliest | 8/8 | 1.0 | 32/32 | 4 / 9 | ok 40 |
| duplicate | 12 | earliest|prec:A|strict | 8/8 | 1.0 | 32/32 | 5 / 9 | ok 40 |
| duplicate | 12 | largest | 8/8 | 1.0 | 32/32 | 3 / 7 | ok 40 |
| duplicate | 12 | largest|prec:A | 8/8 | 1.0 | 32/32 | 6 / 8 | ok 40 |
| duplicate | 12 | largest|prec:A|strict | 8/8 | 1.0 | 32/32 | 4 / 7 | ok 40 |
| duplicate | 12 | largest|prec:B|strict | 8/8 | 1.0 | 32/32 | 5 / 6 | ok 40 |
| duplicate | 12 | largest|strict | 8/8 | 1.0 | 32/32 | 3 / 5 | ok 40 |
| duplicate | 12 | smallest | 8/8 | 1.0 | 32/32 | 4 / 9 | ok 40 |
| duplicate | 12 | smallest|prec:A|strict | 8/8 | 1.0 | 32/32 | 5 / 9 | ok 40 |
| duplicate | 16 | earliest | 8/8 | 1.0 | 32/32 | 6 / 12 | ok 40 |
| duplicate | 16 | earliest|prec:A|strict | 8/8 | 1.0 | 32/32 | 8 / 12 | ok 40 |
| duplicate | 16 | largest | 8/8 | 1.0 | 32/32 | 6 / 8 | ok 40 |
| duplicate | 16 | largest|prec:A | 8/8 | 1.0 | 32/32 | 8 / 13 | ok 40 |
| duplicate | 16 | largest|prec:A|strict | 8/8 | 1.0 | 32/32 | 6 / 10 | ok 40 |
| duplicate | 16 | largest|prec:B|strict | 8/8 | 1.0 | 32/32 | 8 / 11 | ok 40 |
| duplicate | 16 | largest|strict | 8/8 | 1.0 | 32/32 | 4 / 7 | ok 40 |
| duplicate | 16 | smallest | 8/8 | 1.0 | 32/32 | 7 / 14 | ok 40 |
| duplicate | 16 | smallest|prec:A|strict | 8/8 | 1.0 | 32/32 | 8 / 14 | ok 40 |
| expand | 8 | earliest | 1/8 | 2.6 | 17/32 | 12 / 36 | ok 40 |
| expand | 8 | earliest|prec:A|strict | 4/8 | 2.0 | 23/32 | 11 / 28 | ok 40 |
| expand | 8 | largest | 1/8 | 3.0 | 15/32 | 6 / 22 | ok 40 |
| expand | 8 | largest+plain | 1/8 | 2.8 | 15/32 | 7 / 25 | ok 40 |
| expand | 8 | largest|prec:A | 2/8 | 2.4 | 18/32 | 7 / 24 | ok 40 |
| expand | 8 | largest|prec:A|strict | 1/8 | 2.8 | 17/32 | 6 / 21 | ok 40 |
| expand | 8 | largest|prec:B|strict | 1/8 | 2.8 | 17/32 | 6 / 21 | ok 40 |
| expand | 8 | largest|strict | 1/8 | 3.1 | 15/32 | 6 / 20 | ok 40 |
| expand | 8 | smallest | 2/8 | 2.9 | 16/32 | 16 / 41 | ok 40 |
| expand | 8 | smallest|prec:A|strict | 1/8 | 2.6 | 18/32 | 14 / 35 | ok 40 |
| expand | 12 | earliest | 0/8 | 4.6 | 1/32 | 28 / 54 | ok 40 |
| expand | 12 | earliest|prec:A|strict | 1/8 | 3.1 | 8/32 | 23 / 43 | ok 40 |
| expand | 12 | largest | 0/8 | 4.9 | 1/32 | 15 / 32 | ok 40 |
| expand | 12 | largest+plain | 0/8 | 4.5 | 3/32 | 16 / 42 | ok 40 |
| expand | 12 | largest|prec:A | 1/8 | 3.9 | 9/32 | 20 / 43 | ok 40 |
| expand | 12 | largest|prec:A|strict | 1/8 | 3.8 | 7/32 | 15 / 31 | ok 40 |
| expand | 12 | largest|prec:B|strict | 1/8 | 3.9 | 7/32 | 15 / 32 | ok 40 |
| expand | 12 | largest|strict | 0/8 | 4.9 | 1/32 | 14 / 30 | ok 40 |
| expand | 12 | smallest | 0/8 | 4.6 | 2/32 | 34 / 59 | ok 40 |
| expand | 12 | smallest|prec:A|strict | 0/8 | 4.5 | 2/32 | 32 / 53 | ok 40 |
| expand | 16 | earliest | 0/8 | 5.0 | 0/32 | 48 / 77 | ok 40 |
| expand | 16 | earliest|prec:A|strict | 0/8 | 4.2 | 5/32 | 38 / 60 | ok 40 |
| expand | 16 | largest | 0/8 | 5.0 | 0/32 | 28 / 47 | ok 40 |
| expand | 16 | largest+plain | 0/8 | 4.9 | 1/32 | 32 / 63 | ok 40 |
| expand | 16 | largest|prec:A | 0/8 | 4.2 | 4/32 | 33 / 58 | cycle 10, ok 30 |
| expand | 16 | largest|prec:A|strict | 0/8 | 4.8 | 2/32 | 24 / 43 | ok 40 |
| expand | 16 | largest|prec:B|strict | 0/8 | 4.8 | 2/32 | 26 / 43 | ok 40 |
| expand | 16 | largest|strict | 0/8 | 5.0 | 0/32 | 24 / 39 | ok 40 |
| expand | 16 | smallest | 0/8 | 5.0 | 0/32 | 59 / 90 | ok 40 |
| expand | 16 | smallest|prec:A|strict | 0/8 | 5.0 | 0/32 | 50 / 77 | ok 40 |
| mixed | 8 | earliest | 0/8 | 4.6 | 2/32 | 16 / 31 | ok 40 |
| mixed | 8 | earliest|prec:A|strict | 0/8 | 4.9 | 1/32 | 14 / 27 | ok 40 |
| mixed | 8 | largest | 0/8 | 4.6 | 2/32 | 9 / 22 | ok 40 |
| mixed | 8 | largest+plain | 0/8 | 4.8 | 1/32 | 11 / 23 | ok 40 |
| mixed | 8 | largest|prec:A | 0/8 | 4.1 | 4/32 | 12 / 23 | cycle 5, ok 35 |
| mixed | 8 | largest|prec:A|strict | 0/8 | 4.8 | 2/32 | 8 / 22 | ok 40 |
| mixed | 8 | largest|prec:B|strict | 0/8 | 4.8 | 2/32 | 8 / 22 | ok 40 |
| mixed | 8 | largest|strict | 0/8 | 4.8 | 2/32 | 8 / 21 | ok 40 |
| mixed | 8 | smallest | 0/8 | 4.6 | 2/32 | 19 / 42 | ok 40 |
| mixed | 8 | smallest|prec:A|strict | 0/8 | 4.6 | 1/32 | 18 / 35 | ok 40 |
| mixed | 12 | earliest | 0/8 | 5.0 | 0/32 | 31 / 52 | ok 40 |
| mixed | 12 | earliest|prec:A|strict | 0/8 | 4.9 | 0/32 | 25 / 51 | ok 40 |
| mixed | 12 | largest | 0/8 | 5.0 | 0/32 | 19 / 32 | ok 40 |
| mixed | 12 | largest+plain | 0/8 | 5.0 | 0/32 | 24 / 43 | ok 40 |
| mixed | 12 | largest|prec:A | 0/8 | 5.0 | 0/32 | 23 / 41 | cycle 5, ok 35 |
| mixed | 12 | largest|prec:A|strict | 0/8 | 5.0 | 0/32 | 18 / 32 | ok 40 |
| mixed | 12 | largest|prec:B|strict | 0/8 | 5.0 | 0/32 | 18 / 33 | ok 40 |
| mixed | 12 | largest|strict | 0/8 | 5.0 | 0/32 | 16 / 32 | ok 40 |
| mixed | 12 | smallest | 0/8 | 5.0 | 0/32 | 37 / 59 | ok 40 |
| mixed | 12 | smallest|prec:A|strict | 0/8 | 5.0 | 0/32 | 31 / 59 | ok 40 |
| mixed | 16 | earliest | 0/8 | 5.0 | 0/32 | 50 / 78 | ok 40 |
| mixed | 16 | earliest|prec:A|strict | 0/8 | 5.0 | 0/32 | 42 / 68 | ok 40 |
| mixed | 16 | largest | 0/8 | 5.0 | 0/32 | 32 / 56 | ok 40 |
| mixed | 16 | largest+plain | 0/8 | 5.0 | 0/32 | 42 / 69 | ok 40 |
| mixed | 16 | largest|prec:A | 0/8 | 5.0 | 0/32 | 40 / 74 | cycle 8, ok 32 |
| mixed | 16 | largest|prec:A|strict | 0/8 | 5.0 | 0/32 | 30 / 52 | ok 40 |
| mixed | 16 | largest|prec:B|strict | 0/8 | 5.0 | 0/32 | 32 / 52 | ok 40 |
| mixed | 16 | largest|strict | 0/8 | 5.0 | 0/32 | 28 / 49 | ok 40 |
| mixed | 16 | smallest | 0/8 | 5.0 | 0/32 | 60 / 92 | ok 40 |
| mixed | 16 | smallest|prec:A|strict | 0/8 | 5.0 | 0/32 | 50 / 83 | ok 40 |
| reassociate | 8 | earliest | 6/8 | 1.2 | 28/32 | 2 / 4 | ok 40 |
| reassociate | 8 | earliest|prec:A|strict | 6/8 | 1.2 | 28/32 | 2 / 4 | ok 40 |
| reassociate | 8 | largest | 6/8 | 1.2 | 28/32 | 2 / 3 | ok 40 |
| reassociate | 8 | largest|prec:A | 6/8 | 1.2 | 28/32 | 3 / 5 | cycle 5, ok 35 |
| reassociate | 8 | largest|prec:A|strict | 6/8 | 1.2 | 28/32 | 2 / 4 | ok 40 |
| reassociate | 8 | largest|prec:B|strict | 6/8 | 1.2 | 28/32 | 2 / 5 | ok 40 |
| reassociate | 8 | largest|strict | 6/8 | 1.2 | 28/32 | 1 / 3 | ok 40 |
| reassociate | 8 | smallest | 6/8 | 1.2 | 28/32 | 2 / 4 | ok 40 |
| reassociate | 8 | smallest|prec:A|strict | 6/8 | 1.2 | 28/32 | 2 / 4 | ok 40 |
| reassociate | 12 | earliest | 4/8 | 1.5 | 21/32 | 4 / 8 | ok 40 |
| reassociate | 12 | earliest|prec:A|strict | 3/8 | 1.6 | 18/32 | 5 / 9 | ok 40 |
| reassociate | 12 | largest | 4/8 | 1.5 | 21/32 | 4 / 6 | ok 40 |
| reassociate | 12 | largest|prec:A | 4/8 | 1.5 | 21/32 | 6 / 8 | cycle 5, ok 35 |
| reassociate | 12 | largest|prec:A|strict | 4/8 | 1.5 | 21/32 | 5 / 8 | ok 40 |
| reassociate | 12 | largest|prec:B|strict | 4/8 | 1.5 | 21/32 | 5 / 9 | ok 40 |
| reassociate | 12 | largest|strict | 4/8 | 1.5 | 21/32 | 4 / 6 | ok 40 |
| reassociate | 12 | smallest | 4/8 | 1.5 | 21/32 | 4 / 9 | ok 40 |
| reassociate | 12 | smallest|prec:A|strict | 3/8 | 1.6 | 18/32 | 5 / 9 | ok 40 |
| reassociate | 16 | earliest | 5/8 | 1.4 | 23/32 | 4 / 10 | ok 40 |
| reassociate | 16 | earliest|prec:A|strict | 4/8 | 1.5 | 20/32 | 8 / 13 | ok 40 |
| reassociate | 16 | largest | 5/8 | 1.5 | 22/32 | 4 / 6 | ok 40 |
| reassociate | 16 | largest|prec:A | 5/8 | 1.5 | 22/32 | 9 / 16 | cycle 5, ok 35 |
| reassociate | 16 | largest|prec:A|strict | 4/8 | 1.6 | 19/32 | 8 / 10 | ok 40 |
| reassociate | 16 | largest|prec:B|strict | 4/8 | 1.6 | 19/32 | 7 / 10 | ok 40 |
| reassociate | 16 | largest|strict | 4/8 | 1.6 | 19/32 | 3 / 5 | ok 40 |
| reassociate | 16 | smallest | 4/8 | 1.5 | 22/32 | 4 / 11 | ok 40 |
| reassociate | 16 | smallest|prec:A|strict | 3/8 | 1.6 | 19/32 | 8 / 15 | ok 40 |

### Checking the fixed programs, which compile

| rules | inputs | programs | statements, median | median | slowest |
| ----- | ------ | -------- | ------------------ | ------ | ------- |
| earliest | 8 | 240 | 10 | 37.8 µs | 137 µs |
| earliest | 12 | 240 | 18 | 99.8 µs | 249 µs |
| earliest | 16 | 240 | 33 | 463 µs | 756 µs |
| earliest|prec:A|strict | 8 | 240 | 10 | 51.2 µs | 175 µs |
| earliest|prec:A|strict | 12 | 240 | 18 | 143 µs | 416 µs |
| earliest|prec:A|strict | 16 | 240 | 32 | 606 µs | 1.15 ms |
| largest | 8 | 240 | 10 | 37.4 µs | 93.2 µs |
| largest | 12 | 240 | 18 | 98 µs | 269 µs |
| largest | 16 | 240 | 33 | 474 µs | 728 µs |
| largest+plain | 8 | 120 | 11 | 42.5 µs | 81 µs |
| largest+plain | 12 | 120 | 19 | 98.4 µs | 248 µs |
| largest+plain | 16 | 120 | 31 | 458 µs | 706 µs |
| largest|prec:A | 8 | 240 | 10 | 80.2 µs | 278 µs |
| largest|prec:A | 12 | 240 | 18 | 223 µs | 536 µs |
| largest|prec:A | 16 | 240 | 32 | 985 µs | 2.06 ms |
| largest|prec:A|strict | 8 | 240 | 10 | 51.9 µs | 137 µs |
| largest|prec:A|strict | 12 | 240 | 18 | 143 µs | 351 µs |
| largest|prec:A|strict | 16 | 240 | 33 | 603 µs | 1.16 ms |
| largest|prec:B|strict | 8 | 240 | 10 | 49.5 µs | 143 µs |
| largest|prec:B|strict | 12 | 240 | 18 | 139 µs | 367 µs |
| largest|prec:B|strict | 16 | 240 | 33 | 601 µs | 1.14 ms |
| largest|strict | 8 | 240 | 11 | 37.2 µs | 119 µs |
| largest|strict | 12 | 240 | 19 | 101 µs | 261 µs |
| largest|strict | 16 | 240 | 33 | 472 µs | 829 µs |
| smallest | 8 | 240 | 10 | 38.3 µs | 109 µs |
| smallest | 12 | 240 | 18 | 97.8 µs | 250 µs |
| smallest | 16 | 240 | 33 | 459 µs | 822 µs |
| smallest|prec:A|strict | 8 | 240 | 11 | 53.1 µs | 224 µs |
| smallest|prec:A|strict | 12 | 240 | 18 | 143 µs | 399 µs |
| smallest|prec:A|strict | 16 | 240 | 33 | 614 µs | 1.22 ms |

### Does the declared order matter?

| rewrites | programs fixed the same way under orders A and B |
| -------- | ------------------------------------------------ |
| demorgan | 71/120 |
| distribute | 88/120 |
| duplicate | 75/120 |
| expand | 78/120 |
| mixed | 80/120 |
| reassociate | 60/120 |
