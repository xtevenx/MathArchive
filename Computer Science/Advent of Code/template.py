"""AoC 2022 Day ?"""

from utils import get_input, print

INPUT = get_input(__file__)

# Split into lines.
# INPUT = [int(x) for x in INPUT.split("\n")]

# Split into lines, then elements by spaces.
# INPUT = [[int(x) for x in s.split()] for s in INPUT.split("\n")]

# Split into grid of integers.
# INPUT = [[int(x) for x in s] for s in INPUT.split("\n")]

# Split into groups of lines, then lines.
# INPUT = [[int(x) for x in s.split("\n")] for s in INPUT.split("\n\n")]

# Split into groups of lines, then lines, then elements by spaces.
# INPUT = [[[int(y) for y in x.split()] for x in s.split("\n")]
#          for s in INPUT.split("\n\n")]

# Split into groups of lines, then grids of integers.
# INPUT = [[[int(y) for y in x] for x in s.split("\n")]
#          for s in INPUT.split("\n\n")]

if __name__ == "__main__":
    ...
