### Value operations and the library: time per instance

| group | auto | abc_&fraig | abc_&fraig_x | abc_fraig | abc_&cec |
| ----- | ---- | ---------- | ------------ | --------- | -------- |
| op_i128_s1024 | 1.15 ms | 2.76 ms | 20.6 ms | 2.12 ms, 104/105 | 16.8 ms, 5/5 proved |
| op_i128_s16 | 17.4 µs | 434 µs | 1.85 ms | 22.2 µs | 856 µs, 5/5 proved |
| op_i128_s256 | 252 µs | 988 µs | 11.6 ms | 1.01 ms | 5.91 ms, 5/5 proved |
| op_i128_s64 | 48.2 µs | 581 µs | 4.96 ms | 259 µs | 1.68 ms, 5/5 proved |
| op_i12_s1024 | 499 µs | 3.86 ms | 14.1 ms | 2.13 ms | 15.5 ms, 5/5 proved |
| op_i12_s16 | 11.8 µs | 415 µs | 2.01 ms | 22.7 µs | 820 µs, 5/5 proved |
| op_i12_s256 | 135 µs | 938 µs | 7.93 ms | 498 µs | 4.64 ms, 5/5 proved |
| op_i12_s64 | 37.2 µs | 776 µs | 4.41 ms | 414 µs | 1.33 ms, 5/5 proved |
| op_i16_s1024 | 2.79 ms | 5.48 ms | 13.7 ms | 3.09 ms | 14.6 ms, 5/5 proved |
| op_i16_s16 | 5.99 µs | 226 µs | 1.8 ms | 64.6 µs | 749 µs, 5/5 proved |
| op_i16_s256 | 191 µs | 919 µs | 7.26 ms | 706 µs | 4.78 ms, 5/5 proved |
| op_i16_s64 | 27.6 µs | 540 µs | 4.15 ms | 359 µs | 1.23 ms, 5/5 proved |
| op_i20_s1024 | 1.21 ms | 4.21 ms | 13.6 ms | 2.09 ms | 10.6 ms, 5/5 proved |
| op_i20_s16 | 6.65 µs | 328 µs | 1.37 ms | 66.5 µs | 617 µs, 5/5 proved |
| op_i20_s256 | 341 µs | 1.38 ms | 11.7 ms | 720 µs | 3.49 ms, 5/5 proved |
| op_i20_s64 | 34.8 µs | 651 µs | 6.82 ms | 269 µs | 2.77 ms, 5/5 proved |
| op_i24_s1024 | 1.77 ms | 5.87 ms | 15.2 ms | 2.31 ms | 12.6 ms, 5/5 proved |
| op_i24_s16 | 7.5 µs | 311 µs | 2.36 ms | 89.4 µs | 1.23 ms, 5/5 proved |
| op_i24_s256 | 176 µs | 1.17 ms | 10.2 ms | 527 µs | 5.66 ms, 5/5 proved |
| op_i24_s64 | 33.5 µs | 643 µs | 5.02 ms | 282 µs | 2.32 ms, 5/5 proved |
| op_i32_s1024 | 2.78 ms | 6.99 ms | 15.1 ms | 2.83 ms, 123/124 | 12.5 ms, 5/5 proved |
| op_i32_s16 | 6.37 µs | 183 µs | 565 µs | 0 µs | 277 µs, 5/5 proved |
| op_i32_s256 | 329 µs | 1.43 ms | 9.86 ms | 649 µs | 5.63 ms, 5/5 proved |
| op_i32_s64 | 34.5 µs | 667 µs | 6.07 ms | 302 µs | 1.62 ms, 5/5 proved |
| op_i48_s1024 | 3.31 ms | 9.21 ms | 17.3 ms | 3.48 ms, 138/141 | 15.2 ms, 5/5 proved |
| op_i48_s16 | 8.16 µs | 439 µs | 833 µs | 35.6 µs | 219 µs, 5/5 proved |
| op_i48_s256 | 244 µs | 1.13 ms | 12 ms | 677 µs | 5.21 ms, 5/5 proved |
| op_i48_s64 | 41.3 µs | 708 µs | 5.17 ms | 296 µs | 1.73 ms, 5/5 proved |
| op_i4_s1024 | 73.2 µs | 8.67 ms | 11.9 ms | 3.96 ms | 20.1 ms, 5/5 proved |
| op_i4_s16 | 2.25 µs | 281 µs | 2.3 ms | 173 µs | 1.03 ms, 5/5 proved |
| op_i4_s256 | 23.2 µs | 1.25 ms | 6.07 ms | 661 µs | 6.76 ms, 5/5 proved |
| op_i4_s64 | 8.24 µs | 655 µs | 3.59 ms | 120 µs | 2 ms, 5/5 proved |
| op_i64_s1024 | 2.89 ms | 7.08 ms | 20.4 ms | 4.47 ms, 119/132 | 16.6 ms, 5/5 proved |
| op_i64_s16 | 10.9 µs | 396 µs | 1.72 ms | 74.5 µs | 796 µs, 5/5 proved |
| op_i64_s256 | 257 µs | 1.07 ms | 12.6 ms | 716 µs | 4.35 ms, 5/5 proved |
| op_i64_s64 | 33.6 µs | 548 µs | 3.89 ms | 473 µs | 1.95 ms, 5/5 proved |
| op_i8_s1024 | 120 µs | 4.64 ms | 12.8 ms | 2.74 ms | 12.1 ms, 5/5 proved |
| op_i8_s16 | 3.43 µs | 289 µs | 511 µs | 147 µs | 348 µs, 5/5 proved |
| op_i8_s256 | 35.4 µs | 1.27 ms | 7.54 ms | 913 µs | 4.28 ms, 5/5 proved |
| op_i8_s64 | 10.6 µs | 580 µs | 3.41 ms | 194 µs | 1.32 ms, 5/5 proved |
| op_i96_s1024 | 2.98 ms | 7.58 ms | 20.2 ms | 2.98 ms, 104/106 | 17.4 ms, 5/5 proved |
| op_i96_s16 | 13 µs | 335 µs | 657 µs | 169 µs | 414 µs, 5/5 proved |
| op_i96_s256 | 248 µs | 1.22 ms | 14.2 ms | 725 µs | 3.99 ms, 5/5 proved |
| op_i96_s64 | 38.2 µs | 482 µs | 3.73 ms | 151 µs | 1.73 ms, 5/5 proved |
| library | 4.54 µs | 302 µs | 4 ms | 157 µs | 843 µs, 200/200 proved |

### Adversarial instances and programs

| instance | auto | abc_&fraig | abc_&fraig_x | abc_fraig | abc_&cec | `&fraig` memory |
| -------- | ---- | ---------- | ------------ | --------- | -------- | --------------- |
| cmp_b16_c10 | 30.8 ms | 32.4 ms | 13.5 ms | 16.8 ms | 26.8 ms, 1/1 proved | 15.2 MB |
| cmp_b32_c10 | 283 ms | 306 ms | 41.9 ms | 70.3 ms | 114 ms, 1/1 proved | 15.9 MB |
| cmp_b64_c10 | 1.82 s | 1.66 s | 118 ms | 327 ms | 483 ms, 1/1 proved | 20.4 MB |
| cmp_b8_c10 | 1.19 ms | 6.36 ms | 8.56 ms | 4.62 ms | 9.31 ms, 1/1 proved | 14.5 MB |
| hwb_i12 | 104 µs | 3.06 ms | 11.6 ms | 3.54 ms, 0/1 | 6.44 ms, 1/1 proved | 14.7 MB |
| hwb_i16 | 5.01 ms | 8.69 ms | 20 ms | 5.34 ms, 0/1 | 13.2 ms, 1/1 proved | 14.9 MB |
| hwb_i20 | 12.1 ms | 19.2 ms | 31.7 ms | 6.15 ms, 0/1 | 74.5 ms, 1/1 proved | 14.8 MB |
| hwb_i24 | 20.7 ms | 27 ms | 73.6 ms | 6.33 ms, 0/1 | 162 ms, 1/1 proved | 14.8 MB |
| hwb_i28 | 43 ms | 58.6 ms | 128 ms | 5.72 ms, 0/1 | 204 ms, 1/1 proved | 15.3 MB |
| hwb_i32 | 56.6 ms | 139 ms | 199 ms | 13.3 ms, 0/1 | 283 ms, 1/1 proved | 15.6 MB |
| hwb_i40 | 81.1 ms | 341 ms | 601 ms | 10.5 ms, 0/1 | 900 ms, 1/1 proved | 15.4 MB |
| hwb_i8 | 18 µs | 1.39 ms | 10.3 ms | 1.67 ms | 3.01 ms, 1/1 proved | 14.5 MB |
| mult_commuted_b10 | 3.75 s | 86.8 s | timeout | 38.6 ms, 4/20 | 224 s, 1/1 proved | 29 MB |
| mult_commuted_b11 | timeout | timeout | timeout | 49.8 ms, 4/22 | timeout |  |
| mult_commuted_b12 | timeout | timeout | timeout | 51 ms, 4/24 | timeout |  |
| mult_commuted_b3 | 18.2 µs | 622 µs | 7.68 ms | 106 µs | 1.21 ms, 1/1 proved | 14 MB |
| mult_commuted_b4 | 19.1 µs | 1.67 ms | 15.3 ms | 3.95 ms | 3.31 ms, 1/1 proved | 14.2 MB |
| mult_commuted_b5 | 47.4 µs | 9.19 ms | 42.9 ms | 7.5 ms, 5/10 | 14.9 ms, 1/1 proved | 14.5 MB |
| mult_commuted_b6 | 162 µs | 67.6 ms | 276 ms | 11.8 ms, 4/12 | 169 ms, 1/1 proved | 14.7 MB |
| mult_commuted_b7 | 108 ms | 384 ms | 2.03 s | 17.6 ms, 4/14 | 886 ms, 1/1 proved | 15.2 MB |
| mult_commuted_b8 | 222 ms | 2.12 s | 15.1 s | 24.6 ms, 4/16 | 4.97 s, 1/1 proved | 17 MB |
| mult_commuted_b9 | 739 ms | 16.7 s | 122 s | 30.9 ms, 4/18 | 45.6 s, 1/1 proved | 21.6 MB |
| mult_kogge_b10 | 4.81 s | 153 s, 19/20 | timeout | 41.9 ms, 4/20 | 224 s, 1/1 proved | 32.1 MB |
| mult_kogge_b11 | timeout | timeout | timeout | 41.6 ms, 4/22 | timeout |  |
| mult_kogge_b12 | timeout | timeout | timeout | 50.4 ms, 4/24 | timeout |  |
| mult_kogge_b3 | 9.28 µs | 985 µs | 6.43 ms | 400 µs | 1.59 ms, 1/1 proved | 13.9 MB |
| mult_kogge_b4 | 20.4 µs | 2.2 ms | 14.4 ms | 4.45 ms, 7/8 | 3.55 ms, 1/1 proved | 14.3 MB |
| mult_kogge_b5 | 51.2 µs | 12.8 ms | 43.8 ms | 8.83 ms, 5/10 | 19.3 ms, 1/1 proved | 14 MB |
| mult_kogge_b6 | 187 µs | 82.2 ms | 297 ms | 13.1 ms, 4/12 | 245 ms, 1/1 proved | 14.8 MB |
| mult_kogge_b7 | 121 ms | 500 ms | 2.31 s | 18.3 ms, 4/14 | 1.13 s, 1/1 proved | 15.7 MB |
| mult_kogge_b8 | 276 ms | 3.53 s | 18.7 s | 25.1 ms, 4/16 | 5.53 s, 1/1 proved | 17.6 MB |
| mult_kogge_b9 | 976 ms | 21.4 s | 139 s | 29 ms, 4/18 | 46.2 s, 1/1 proved | 20.8 MB |
| parity_i128_c3 | 21.9 ms | 27.6 s, 1/3 | 93.3 s, 1/3 | 3.68 ms, 0/3 | 1.15 s, 1/1 proved | 38.1 MB |
| parity_i12_c3 | 40.3 µs | 2.06 ms | 20.9 ms | 812 µs, 1/3 | 4.17 ms, 1/1 proved | 13.9 MB |
| parity_i16_c3 | 8.69 ms | 17 ms | 50 ms | 1.52 ms, 1/3 | 15.2 ms, 1/1 proved | 14.2 MB |
| parity_i20_c3 | 7.57 ms | 7.44 ms | 49.6 ms | 2.96 ms, 1/3 | 23 ms, 1/1 proved | 14.3 MB |
| parity_i24_c3 | 8.33 ms | 490 ms | 4.5 s | 868 µs, 0/3 | 62 ms, 1/1 proved | 16.6 MB |
| parity_i28_c3 | 8.54 ms | 95.3 ms | 59.2 s, 2/3 | 754 µs, 0/3 | 430 ms, 1/1 proved | 15.6 MB |
| parity_i32_c3 | 8.99 ms | 80.5 ms | 87.9 s, 2/3 | 2.93 ms, 0/3 | 278 ms, 1/1 proved | 15.8 MB |
| parity_i40_c3 | 11 ms | 14.9 s, 2/3 | 113 s, 2/3 | 1.35 ms, 0/3 | 1.48 s, 1/1 proved | 22.7 MB |
| parity_i48_c3 | 10.5 ms | 31.3 s, 1/3 | 92.2 s, 1/3 | 1.86 ms, 0/3 | 1.42 s, 1/1 proved | 28.7 MB |
| parity_i64_c3 | 12.7 ms | 44.1 s, 1/3 | 191 s, 1/3 | 3.23 ms, 0/3 | 1.52 s, 1/1 proved | 35.5 MB |
| parity_i8_c3 | 8.81 µs | 1.39 ms | 12.8 ms | 1.02 ms | 1.99 ms, 1/1 proved | 14.3 MB |
| parity_i96_c3 | 17.5 ms | 26.1 s, 1/3 | 123 s, 1/3 | 3.86 ms, 0/3 | 1.02 s, 1/1 proved | 36.8 MB |
| tangle_i16_s1024_0 | 533 µs | 2.88 ms | 8.29 ms | 3.62 ms | 7.2 ms, 1/1 proved | 13.9 MB |
| tangle_i16_s1024_1 | 1.03 ms | 2.94 ms | 11.3 ms | 1.41 ms | 7.06 ms, 1/1 proved | 14 MB |
| tangle_i16_s1024_2 | 570 µs | 1.78 ms | 9.78 ms | 952 µs | 6.62 ms, 1/1 proved | 14 MB |
| tangle_i16_s256_0 | 111 µs | 1.03 ms | 3.76 ms | 346 µs | 3 ms, 1/1 proved | 14.2 MB |
| tangle_i16_s256_1 | 79.3 µs | 924 µs | 5.69 ms | 420 µs | 3.33 ms, 1/1 proved | 13.7 MB |
| tangle_i16_s256_2 | 219 µs | 875 µs | 6.61 ms | 504 µs | 3.99 ms, 1/1 proved | 14 MB |
| tangle_i32_s1024_0 | 1.21 ms | 4.25 ms | 16.8 ms | 1.08 ms | 4.15 ms, 1/1 proved | 14.2 MB |
| tangle_i32_s1024_1 | 772 µs | 2.15 ms | 8.54 ms | 1.78 ms | 5.87 ms, 1/1 proved | 14 MB |
| tangle_i32_s1024_2 | 620 µs | 2.4 ms | 11.1 ms | 1.86 ms | 7.27 ms, 1/1 proved | 13.4 MB |
| tangle_i32_s256_0 | 98.6 µs | 1.27 ms | 5.86 ms | 707 µs | 3.38 ms, 1/1 proved | 14 MB |
| tangle_i32_s256_1 | 113 µs | 1.06 ms | 6.16 ms | 132 µs | 3.16 ms, 1/1 proved | 14 MB |
| tangle_i32_s256_2 | 173 µs | 1.25 ms | 7.5 ms | 668 µs | 2.87 ms, 1/1 proved | 13.7 MB |
| tangle_i64_s1024_0 | 1.7 ms | 3.36 ms | 11 ms | 2.46 ms | 7.17 ms, 1/1 proved | 14.7 MB |
| tangle_i64_s1024_1 | 1.58 ms | 2.77 ms | 11.4 ms | 4.41 ms, 42/43 | 7.66 ms, 1/1 proved | 14.6 MB |
| tangle_i64_s1024_2 | 962 µs | 3.69 ms | 10 ms | 2.16 ms | 6.38 ms, 1/1 proved | 14.7 MB |
| tangle_i64_s256_0 | 110 µs | 878 µs | 4.76 ms | 768 µs | 3.25 ms, 1/1 proved | 13.7 MB |
| tangle_i64_s256_1 | 156 µs | 1.32 ms | 5.7 ms | 969 µs | 4.39 ms, 1/1 proved | 13.9 MB |
| tangle_i64_s256_2 | 184 µs | 1.11 ms | 6.19 ms | 409 µs | 3.02 ms, 1/1 proved | 13.9 MB |
| program_t200_c1000 | 48.3 ms | 54 ms | 38.3 ms | 59.2 ms | 322 ms, 1/1 proved | 17.2 MB |
| program_t200_c1000_r50 | 12.1 ms | 3.03 ms | 10.3 ms | 2.02 ms | 22 ms, 1/1 proved | 14.4 MB |
| program_t200_c4000_r50 | 108 ms | 87 ms | 35.9 ms | 111 ms | 703 ms, 1/1 proved | 17.3 MB |
| program_t200_c4000 | 301 ms | 264 ms | 96.5 ms | 521 ms | 2.39 s, 1/1 proved | 19.8 MB |
| program_t200_c16000_r50 | 1.02 s | 201 ms | 76.8 ms | 880 ms | 1.94 s, 1/1 proved | 22.3 MB |
| program_t200_c16000 | 3.23 s | 8.56 s | 2.85 s | 18.1 s | 11.7 s, 1/1 proved | 33.1 MB |
| program_t200_c64000_r50 | 5.23 s | 1.83 s | 408 ms | 11.7 s | 9.33 s, 1/1 proved | 37.5 MB |
| program_t200_c64000 | 36 s | 324 s | 40.3 s | 526 s | 132 s, 1/1 proved | 92.6 MB |
| program_t200_c256000_r50 | 22.1 s | 10.9 s | 2.69 s | 194 s | 52.2 s, 1/1 proved | 106 MB |
| program_t200_c256000 | 393 s | timeout | 661 s | timeout | out of memory |  |
| program_t200_c1000000_r50 | 137 s | 69.7 s | 12.1 s | timeout | out of memory | 347 MB |
