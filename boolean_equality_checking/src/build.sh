#!/bin/sh
# Builds the beq binary next to this script.
set -eu
cd "$(dirname "$0")"
g++ -std=c++20 -O2 -march=native -fno-strict-aliasing -Wall -Wextra -o beq main.cpp
