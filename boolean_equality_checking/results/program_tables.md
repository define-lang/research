| instance | method | `and` nodes | time | peak memory | redundant nodes | planted found | SAT |
| -------- | ------ | ----------- | ---- | ----------- | --------------- | ------------- | --- |
| program_t200_c1000 | norm_single | 10,267 | 1.05 ms | 17.4 MB | 516 | 36/49 |  |
| program_t200_c1000_r50 | norm_single | 6,961 | 665 µs | 17.4 MB | 394 | 27/35 |  |
| program_t200_c1000 | portfolio | 10,267 | 53.6 ms | 17.4 MB | 3,617 | 49/49 | sat_calls=4289, sat_different=47, cex_flushes=0 |
| program_t200_c1000_r50 | portfolio | 6,961 | 14.2 ms | 17.4 MB | 2,602 | 35/35 | sat_calls=2431, sat_different=23, cex_flushes=0 |
| program_t200_c1000 | strash | 10,267 | 144 µs | 17.4 MB | 451 | 36/49 |  |
| program_t200_c1000_r50 | strash | 6,961 | 102 µs | 17.4 MB | 355 | 26/35 |  |
| program_t200_c1000 | sweep | 10,267 | 45.5 ms | 17.4 MB | 3,617 | 49/49 | sat_calls=5061, sat_different=47, cex_flushes=0 |
| program_t200_c1000_r50 | sweep | 6,961 | 12.1 ms | 17.4 MB | 2,602 | 35/35 | sat_calls=3677, sat_different=23, cex_flushes=0 |
| program_t200_c1000 | sweep_unscoped | 10,267 | 36.5 ms | 17.4 MB | 3,617 | 49/49 | sat_calls=5063, sat_different=48, cex_flushes=0 |
| program_t200_c1000_r50 | sweep_unscoped | 6,961 | 12.9 ms | 17.4 MB | 2,602 | 35/35 | sat_calls=3680, sat_different=25, cex_flushes=0 |
| program_t200_c4000 | norm_single | 34,387 | 3.83 ms | 17.4 MB | 1,320 | 86/118 |  |
| program_t200_c4000_r50 | norm_single | 30,158 | 3.37 ms | 17.4 MB | 1,284 | 82/112 |  |
| program_t200_c4000 | portfolio | 34,387 | 307 ms | 24 MB | 11,315 | 118/118 | sat_calls=14733, sat_different=112, cex_flushes=1 |
| program_t200_c4000_r50 | portfolio | 30,158 | 118 ms | 19.9 MB | 10,475 | 112/112 | sat_calls=11297, sat_different=65, cex_flushes=1 |
| program_t200_c4000 | strash | 34,387 | 438 µs | 17.4 MB | 1,134 | 86/118 |  |
| program_t200_c4000_r50 | strash | 30,158 | 424 µs | 17.4 MB | 1,114 | 80/112 |  |
| program_t200_c4000 | sweep | 34,387 | 271 ms | 23.4 MB | 11,315 | 118/118 | sat_calls=16721, sat_different=110, cex_flushes=1 |
| program_t200_c4000_r50 | sweep | 30,158 | 105 ms | 21.5 MB | 10,475 | 112/112 | sat_calls=15165, sat_different=65, cex_flushes=1 |
| program_t200_c4000 | sweep_unscoped | 34,387 | 211 ms | 22.8 MB | 11,315 | 118/118 | sat_calls=16715, sat_different=107, cex_flushes=1 |
| program_t200_c4000_r50 | sweep_unscoped | 30,158 | 129 ms | 20.6 MB | 10,475 | 112/112 | sat_calls=15161, sat_different=63, cex_flushes=0 |
| program_t200_c16000 | norm_single | 146,197 | 18.1 ms | 23.8 MB | 6,245 | 362/489 |  |
| program_t200_c16000_r50 | norm_single | 119,428 | 15.5 ms | 20 MB | 5,278 | 308/421 |  |
| program_t200_c16000 | portfolio | 146,197 | 3.44 s | 76.1 MB | 48,243 | 489/489 | sat_calls=64007, sat_different=466, cex_flushes=7 |
| program_t200_c16000_r50 | portfolio | 119,428 | 1.11 s | 68.9 MB | 41,842 | 421/421 | sat_calls=45026, sat_different=202, cex_flushes=3 |
| program_t200_c16000 | strash | 146,197 | 2.55 ms | 17.4 MB | 5,358 | 350/489 |  |
| program_t200_c16000_r50 | strash | 119,428 | 1.89 ms | 17.4 MB | 4,600 | 303/421 |  |
| program_t200_c16000 | sweep | 146,197 | 3.26 s | 75.4 MB | 48,243 | 489/489 | sat_calls=70455, sat_different=469, cex_flushes=7 |
| program_t200_c16000_r50 | sweep | 119,428 | 1.03 s | 70.1 MB | 41,842 | 421/421 | sat_calls=60250, sat_different=208, cex_flushes=3 |
| program_t200_c16000 | sweep_unscoped | 146,197 | 2.83 s | 74.3 MB | 48,243 | 489/489 | sat_calls=70451, sat_different=461, cex_flushes=7 |
| program_t200_c16000_r50 | sweep_unscoped | 119,428 | 1.23 s | 68 MB | 41,842 | 421/421 | sat_calls=60242, sat_different=204, cex_flushes=3 |
| program_t200_c64000 | norm_single | 560,594 | 118 ms | 81.4 MB | 25,091 | 1482/2029 |  |
| program_t200_c64000_r50 | norm_single | 478,430 | 142 ms | 69.1 MB | 21,826 | 1283/1743 |  |
| program_t200_c64000 | portfolio | 560,594 | 35.6 s | 280 MB | 186,137 | 2029/2029 | sat_calls=244485, sat_different=1159, cex_flushes=18 |
| program_t200_c64000_r50 | portfolio | 478,430 | 5.56 s | 159 MB | 167,491 | 1743/1743 | sat_calls=177692, sat_different=623, cex_flushes=9 |
| program_t200_c64000 | strash | 560,594 | 17.8 ms | 42.1 MB | 21,830 | 1443/2029 |  |
| program_t200_c64000_r50 | strash | 478,430 | 15.7 ms | 39.1 MB | 18,963 | 1249/1743 |  |
| program_t200_c64000 | sweep | 560,594 | 32.6 s | 274 MB | 186,137 | 2029/2029 | sat_calls=269547, sat_different=1184, cex_flushes=18 |
| program_t200_c64000_r50 | sweep | 478,430 | 4.61 s | 158 MB | 167,491 | 1743/1743 | sat_calls=241900, sat_different=616, cex_flushes=9 |
| program_t200_c64000 | sweep_unscoped | 560,594 | 39 s | 275 MB | 186,137 | 2029/2029 | sat_calls=269574, sat_different=1209, cex_flushes=18 |
| program_t200_c64000_r50 | sweep_unscoped | 478,430 | 6.01 s | 160 MB | 167,491 | 1743/1743 | sat_calls=241976, sat_different=649, cex_flushes=10 |
| program_t200_c256000 | norm_single | 2,190,421 | 1.05 s | 308 MB | 97,863 | 5725/7905 |  |
| program_t200_c256000_r50 | norm_single | 1,849,727 | 753 ms | 259 MB | 85,052 | 5034/6875 |  |
| program_t200_c256000 | portfolio | 2,190,421 | 370 s | 983 MB | 729,130 | 7905/7905 | sat_calls=954214, sat_different=2606, cex_flushes=40 |
| program_t200_c256000_r50 | portfolio | 1,849,727 | 23.1 s | 425 MB | 654,191 | 6875/6875 | sat_calls=689420, sat_different=1452, cex_flushes=22 |
| program_t200_c256000 | strash | 2,190,421 | 119 ms | 155 MB | 84,649 | 5543/7905 |  |
| program_t200_c256000_r50 | strash | 1,849,727 | 74.3 ms | 96.1 MB | 73,851 | 4886/6875 |  |
| program_t200_c256000 | sweep | 2,190,421 | 369 s | 1.02 GB | 729,130 | 7905/7905 | sat_calls=1054050, sat_different=2553, cex_flushes=39 |
| program_t200_c256000_r50 | sweep | 1,849,727 | 20.9 s | 389 MB | 654,191 | 6875/6875 | sat_calls=942406, sat_different=1434, cex_flushes=22 |
| program_t200_c1000000 | norm_single | 8,259,997 | 4.38 s | 1.15 GB | 369,901 | 22036/30159 |  |
| program_t200_c1000000_r50 | norm_single | 7,018,550 | 3.92 s | 981 MB | 313,325 | 18879/25680 |  |
| program_t200_c1000000_r50 | portfolio | 7,018,550 | 126 s | 1.44 GB | 2,468,172 | 25680/25680 | sat_calls=2591186, sat_different=3199, cex_flushes=50 |
| program_t200_c1000000 | strash | 8,259,997 | 458 ms | 599 MB | 320,060 | 21364/30159 |  |
| program_t200_c1000000_r50 | strash | 7,018,550 | 358 ms | 365 MB | 271,262 | 18361/25680 |  |
| program_t200_c1000000_r50 | sweep | 7,018,550 | 120 s | 1.41 GB | 2,468,172 | 25680/25680 | sat_calls=3567676, sat_different=3201, cex_flushes=50 |
