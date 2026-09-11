Ratios relative to limit_256; lower is better. Cases include scale and seed.
Only compare aggregate scores with equal coverage and no failures.

| Pair/control | Cases | Failures | CPU geomean | Peak RSS geomean | Worst CPU | Worst RSS |
| --- | --- | --- | --- | --- | --- | --- |
| limit_32 | 77/77 | 0 | 0.951 | 0.900 | 1.693 (dense_64:s1:seed74921) | 1.013 (library_fanout:s1:seed74921) |
| limit_16 | 77/77 | 0 | 0.951 | 0.888 | 1.913 (overlap_16:s1:seed74921) | 1.010 (dense_1:s1:seed74921) |
| limit_8 | 77/77 | 0 | 0.952 | 0.882 | 1.660 (dense_64:s1:seed74921) | 1.013 (short_1:s1:seed74921) |
| limit_64 | 77/77 | 0 | 0.960 | 0.917 | 1.704 (dense_64:s1:seed74921) | 1.005 (read_8:s1:seed74921) |
| limit_4 | 77/77 | 0 | 0.963 | 0.881 | 1.773 (dense_64:s1:seed74921) | 1.011 (dense_1:s1:seed74921) |
| limit_128 | 77/77 | 0 | 0.970 | 0.950 | 1.696 (unchanged_128:s1:seed74921) | 1.013 (library_fanout:s1:seed74921) |
| limit_1 | 77/77 | 0 | 0.976 | 0.881 | 1.666 (dense_64:s1:seed74921) | 1.011 (dense_1:s1:seed74921) |
| limit_256 | 77/77 | 0 | 1.000 | 1.000 | 1.000 (wide_registry:s1:seed74921) | 1.000 (wide_registry:s1:seed74921) |
