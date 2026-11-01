
### operations

220 instances; auto / fastest exact method: median 1.06, 90th percentile 1.92, max 5.58
auto faster than or equal to every exact method on 40
paths taken: {'sweep': 160, 'tt': 60}; unfinished: []
- op_i20_s256_w8_4: 3.67 times (228 µs against bdd_natural 62.1 µs)
- op_i16_s1024_w8_0: 3.93 times (2.22 ms against bdd_first_use 565 µs)
- op_i16_s256_w8_3: 5.58 times (302 µs against bdd_first_use 54.1 µs)

### adversarial

58 instances; auto / fastest exact method: median 1.17, 90th percentile 87.39, max 261.05
auto faster than or equal to every exact method on 15
paths taken: {'sweep': 46, 'tt': 12}; unfinished: ['mult_commuted_b11', 'mult_commuted_b12', 'mult_kogge_b11', 'mult_kogge_b12']
- mult_commuted_b7: 142.42 times (108 ms against tt 755 µs)
- parity_i20_c3: 154.04 times (7.57 ms against bdd_first_use 49.2 µs)
- parity_i16_c3: 261.05 times (8.69 ms against bdd_natural 33.3 µs)

### library

200 instances; auto / fastest exact method: median 0.97, 90th percentile 1.05, max 1.65
auto faster than or equal to every exact method on 144
paths taken: {'tt': 200}; unfinished: []
- library_004: 1.46 times (13.4 µs against bdd_first_use 9.2 µs)
- library_002: 1.52 times (7.22 µs against tt 4.74 µs)
- library_105: 1.65 times (0.79 µs against tt 0.48 µs)

### program

11 instances; auto / fastest exact method: median 1.01, 90th percentile 1.10, max 1.13
auto faster than or equal to every exact method on 2
paths taken: {'sweep': 11}; unfinished: []
- program_t200_c64000_r50: 1.09 times (5.23 s against sweep 4.81 s)
- program_t200_c1000_r50: 1.10 times (12.1 ms against portfolio 11 ms)
- program_t200_c64000: 1.13 times (36 s against sweep 31.9 s)
