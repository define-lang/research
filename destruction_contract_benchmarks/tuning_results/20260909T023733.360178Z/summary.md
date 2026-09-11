Ratios relative to 256/1024; lower is better. Cases include scale and seed.
Only compare aggregate scores with equal coverage and no failures.

| Pair/control | Cases | Failures | CPU geomean | Peak RSS geomean | Worst CPU | Worst RSS |
| --- | --- | --- | --- | --- | --- | --- |
| 64/128 | 23/23 | 0 | 0.941 | 1.016 | 1.266 (batch_updates:s4:seed74921) | 3.097 (batch_updates:s4:seed74921) |
| 64/256 | 23/23 | 0 | 0.942 | 0.981 | 1.084 (medium_512:s4:seed74921) | 2.061 (batch_updates:s4:seed74921) |
| 128/128 | 23/23 | 0 | 0.946 | 1.041 | 1.243 (batch_updates:s4:seed74921) | 3.095 (batch_updates:s4:seed74921) |
| 256/128 | 23/23 | 0 | 0.957 | 1.045 | 1.268 (batch_updates:s4:seed74921) | 3.090 (batch_updates:s4:seed74921) |
| 128/256 | 23/23 | 0 | 0.958 | 1.004 | 1.097 (fanout_512:s4:seed74921) | 2.063 (batch_updates:s4:seed74921) |
| 256/256 | 23/23 | 0 | 0.963 | 1.010 | 1.057 (medium_2048:s4:seed74921) | 2.062 (batch_updates:s4:seed74921) |
| 32/128 | 23/23 | 0 | 0.969 | 1.024 | 1.407 (medium_2048:s4:seed74921) | 3.097 (batch_updates:s4:seed74921) |
| 64/1024 | 23/23 | 0 | 0.977 | 0.965 | 1.070 (sparse_updates:s4:seed74921) | 1.004 (sparse_updates:s4:seed74921) |
| 64/512 | 23/23 | 0 | 0.983 | 0.962 | 1.232 (batch_updates:s4:seed74921) | 1.364 (batch_updates:s4:seed74921) |
| 256/512 | 23/23 | 0 | 0.985 | 0.994 | 1.225 (batch_updates:s4:seed74921) | 1.364 (batch_updates:s4:seed74921) |
| 128/1024 | 23/23 | 0 | 0.985 | 0.988 | 1.055 (overlap_updates:s4:seed74921) | 1.003 (medium_128:s4:seed74921) |
| 128/512 | 23/23 | 0 | 0.986 | 0.984 | 1.227 (batch_updates:s4:seed74921) | 1.364 (batch_updates:s4:seed74921) |
| 32/256 | 23/23 | 0 | 0.993 | 0.997 | 1.522 (medium_2048:s4:seed74921) | 2.057 (batch_updates:s4:seed74921) |
| 256/1024 | 23/23 | 0 | 1.000 | 1.000 | 1.000 (wide_registry:s4:seed74921) | 1.000 (wide_registry:s4:seed74921) |
| 32/512 | 23/23 | 0 | 1.044 | 0.996 | 1.826 (medium_2048:s4:seed74921) | 1.364 (batch_updates:s4:seed74921) |
| 32/1024 | 23/23 | 0 | 1.115 | 1.045 | 2.572 (medium_2048:s4:seed74921) | 1.680 (medium_128:s4:seed74921) |
