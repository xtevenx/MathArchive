#pragma GCC optimize("O3")
#pragma GCC optimize("unroll-loops")
#pragma GCC optimize("fast-math")

#pragma GCC target("avx2")
//#pragma GCC target("sse4.2")
//#pragma GCC target("mmx")

#pragma GCC target("popcnt,lzcnt")
#define popcnt __builtin_popcount
#define lzcnt __builtin_clz

#include <algorithm>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>


int abs(int n) { return n >= 0 ? n : -n; }
bool ascending(int n, int m) { return n < m; }
bool descending(int n, int m) { return n > m; }


int main() {
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(nullptr);

    // good luck! :D

    return 0;
}
