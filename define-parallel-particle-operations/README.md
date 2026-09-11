This is an archive of a bunch of code I wrote for about 500 hours over two months that I realized was not necessary at that time, but may become necessary in the future, if and when we need to do parallel memory rearrangement at runtime.

While working through a petri net representation of our operations, I realized that symbolic operations will have an entirely different dependency model that will not require any of this particle-operation dependency stuff at all.

This was an implementation of DLP 44: Deterministic Automatic Concurrency.
