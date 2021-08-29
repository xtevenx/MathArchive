import enum
from copy import deepcopy

from enum import Enum
from typing import Any, Callable, List, Sequence


class QueryType(Enum):
    # Name: Accumulation
    # Description:
    #   Query type for functions which are accumulators. You may also
    #   know these from use in the reduce() function. These functions
    #   do not work properly if one of the elements is operated on more
    #   than once, so special care needs to be put in when querying the
    #   sparse table.
    # Example: sum(), product(), etc.
    # Time complexity: O(log(n))
    ACCUMULATION = enum.auto()

    # Name: Comparison
    # Description:
    #   Query type for functions which are comparisons. You may also
    #   know these from use as comparison functions in sorting
    #   algorithms. These functions still work if elements are operated
    #   on more than once.
    # Example: min(), max(), etc.
    # Time complexity: O(1)
    COMPARISON = enum.auto()


class SparseTable:
    def __init__(self, seq: Sequence, func: Callable) -> None:
        # Save the parameters. `_seq' is used in `_generate_table()'
        # and `_func' is used in various places.
        self._seq: Sequence = seq
        self._func: Callable = func

        # Save some general purpose variables.
        self._length: int = len(self._seq)

        # Set the type of the sparse table, then generate it.
        self._table: List[List]
        self._generate_table()

    def _generate_table(self) -> None:
        # Set base case for sparse table. `deepcopy' is used for each
        # element to make sure stupid things don't happen.
        self._table = [[deepcopy(x) for x in self._seq]]

        # Generate the rest of the table.
        self._table.extend(
            [
                self._func(self._table[i - 1][j], self._table[i - 1][j + (1 << (i - 1))])
                for j in range(self._length - (1 << i) + 1)
            ] for i in range(1, self._length.bit_length())
        )

    def __str__(self) -> str:
        ret: str = ""
        for i, row in enumerate(self._table):
            prefix_str: str = "[" if (i == 0) else " "
            suffix_str: str = "]" if (i == len(self._table) - 1) else "\n"
            ret += f"{prefix_str}{row}{suffix_str}"
        return ret

    def query(self, start_index: int, length: int, query_type: QueryType = QueryType.ACCUMULATION) -> Any:
        # Sanity check to ensure the starting index is valid.
        if start_index < -self._length:
            raise IndexError(f"Index {start_index} is less than the minimum index.")
        if start_index >= self._length:
            raise IndexError(f"Index {start_index} is greater than the maximum index.")

        # Sanity check to ensure the length is valid.
        if length <= 0:
            raise IndexError("Length is not positive.")

        # Adapt any negative starting indices.
        start_index += (start_index < 0) * len(self._table[0])

        # Shorten the length is it goes past the end.
        length = min(length, len(self._table[0]) - start_index)

        # Call the correct query function.
        query_func = self._query_acc if query_type == QueryType.ACCUMULATION else self._query_cmp
        return query_func(start_index, length)

    def _query_acc(self, start_index: int, length: int) -> Any:
        log_2: int = length.bit_length() - 1

        # If the length is an order of 2, then just return it.
        if not length & (length - 1):
            return self._table[log_2][start_index]

        # Call the accumulator function on the largest order 2 length
        # and the accumulation of the rest.
        return self._func(
            self._table[log_2][start_index],
            self._query_acc(start_index + (1 << log_2), length - (1 << log_2))
        )

    def _query_cmp(self, start_index: int, length: int) -> Any:
        log_2: int = length.bit_length() - 1

        # Call the function on the two ranges that cover the front and
        # end of the total range.
        return self._func(
            self._table[log_2][start_index],
            self._table[log_2][start_index + length - (1 << log_2)]
        )


if __name__ == "__main__":
    ...
