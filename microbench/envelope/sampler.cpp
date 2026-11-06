// Independent exhaustive envelope sampler for a single unordered reduction.
// Input: first line "seed <8-hex-digit binary32 bits>", second line "n <count>",
// then n lines of binary32 bits. Output: JSON with the sorted double-bit support.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <set>
#include <sstream>
#include <string>
#include <vector>

static double f32(double x) {
    float y = static_cast<float>(x);
    return static_cast<double>(y);
}

static double canonical(double x) { return x == 0.0 ? 0.0 : x; }

static uint64_t dbits(double x) {
    uint64_t u;
    std::memcpy(&u, &x, sizeof(u));
    return u;
}

static uint32_t parse_hex(const std::string &text) {
    return static_cast<uint32_t>(std::stoul(text, nullptr, 16));
}

static float from_bits(uint32_t bits) {
    float value;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
}

static std::set<double> support(const std::vector<double> &leaves) {
    const size_t n = leaves.size();
    std::vector<std::vector<std::set<double>>> table(n, std::vector<std::set<double>>(n));
    for (size_t i = 0; i < n; ++i) table[i][i].insert(canonical(leaves[i]));
    for (size_t length = 2; length <= n; ++length) {
        for (size_t start = 0; start + length <= n; ++start) {
            const size_t end = start + length - 1;
            std::set<double> values;
            for (size_t split = start; split < end; ++split) {
                for (double a : table[start][split]) {
                    for (double b : table[split + 1][end]) {
                        const double total = a + b;
                        values.insert(canonical(f32(total)));
                        values.insert(canonical(total));
                    }
                }
            }
            table[start][end] = std::move(values);
        }
    }
    return table[0][n - 1];
}

int main(int argc, char **argv) {
    if (argc != 2) {
        std::cerr << "usage: vfg-envelope-sampler INPUT\n";
        return 2;
    }
    std::ifstream input(argv[1]);
    if (!input) {
        std::cerr << "cannot open input\n";
        return 2;
    }
    std::string key;
    uint32_t seed_bits = 0;
    size_t n = 0;
    input >> key >> std::hex >> seed_bits;
    input >> key >> std::dec >> n;
    std::vector<double> leaves;
    leaves.push_back(static_cast<double>(from_bits(seed_bits)));
    for (size_t i = 0; i < n; ++i) {
        uint32_t bits = 0;
        input >> std::hex >> bits;
        leaves.push_back(static_cast<double>(from_bits(bits)));
    }
    if (!input) {
        std::cerr << "malformed input\n";
        return 2;
    }
    const std::set<double> values = support(leaves);
    std::cout << "{\"leaves\":" << leaves.size() << ",\"support_size\":" << values.size()
              << ",\"values\":[";
    bool first = true;
    for (double value : values) {
        if (!first) std::cout << ",";
        first = false;
        std::cout << "\"" << std::hex << std::setw(16) << std::setfill('0') << dbits(value) << "\"";
    }
    std::cout << "]}\n";
    return 0;
}
