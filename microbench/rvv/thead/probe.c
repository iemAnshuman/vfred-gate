/* Ordered vs unordered FP32 reduction on an RVV 0.7.1 (XTheadVector) core.
   Self-check: the ordered result must equal the scalar left fold on every array. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

void vfg_thead_reduce(const float *x, size_t n, const float *zero, float *out, int ordered);
size_t vfg_thead_vlmax(size_t n);

static uint32_t bits(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }
static uint64_t state = 0x9e3779b97f4a7c15ULL;
static uint64_t rnd(void) { state ^= state << 13; state ^= state >> 7; state ^= state << 17; return state; }
static float value(void) {
    uint64_t r = rnd();
    float m = 1.0f + (float)(r & 0x7fffff) * 0x1p-23f;
    int e = (int)((r >> 23) % 17) - 8;
    float v = m;
    while (e > 0) { v *= 2.0f; --e; }
    while (e < 0) { v *= 0.5f; ++e; }
    return (r >> 40) & 1 ? -v : v;
}
static float scalar(const float *x, size_t n) { float s = 0.0f; for (size_t i = 0; i < n; ++i) s += x[i]; return s; }
static const float zero = 0.0f;
static float run(const float *x, size_t n, int ordered) { float o; vfg_thead_reduce(x, n, &zero, &o, ordered); return o; }

/* Dump mode: small arrays with all inputs, for offline legal-envelope checks. */
static int dump(void) {
    printf("vlmax_e32m1=%zu\n", vfg_thead_vlmax(1024));
    float x[12];
    for (int t = 0; t < 300; ++t) {
        size_t n = 2 + rnd() % 11;
        for (size_t i = 0; i < n; ++i) x[i] = value();
        printf("rec %d %zu %08x %08x %08x", t, n, bits(scalar(x, n)), bits(run(x, n, 1)), bits(run(x, n, 0)));
        for (size_t i = 0; i < n; ++i) printf(" %08x", bits(x[i]));
        printf("\n");
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "dump") == 0) return dump();
    /* Fixed case: order changes the answer. Left fold gives 1, a pairwise tree gives 2. */
    float fixed[4] = {1e8f, 1.0f, -1e8f, 1.0f};
    printf("fixed scalar=%08x ordered=%08x unordered=%08x\n",
           bits(scalar(fixed, 4)), bits(run(fixed, 4, 1)), bits(run(fixed, 4, 0)));
    enum { TRIALS = 20000, MAXN = 64 };
    float x[MAXN];
    unsigned long ordered_ok = 0, differ = 0, invocations = 0;
    int shown = 0;
    for (int t = 0; t < TRIALS; ++t) {
        size_t n = 1 + rnd() % MAXN;
        for (size_t i = 0; i < n; ++i) x[i] = value();
        float s = scalar(x, n), o = run(x, n, 1), u = run(x, n, 0);
        invocations += 2;
        if (bits(o) == bits(s)) ++ordered_ok;
        if (bits(u) != bits(o)) {
            ++differ;
            if (shown < 5) { printf("diff trial=%d n=%zu ordered=%08x unordered=%08x\n", t, n, bits(o), bits(u)); ++shown; }
        }
    }
    printf("trials=%d invocations=%lu ordered_equals_scalar=%lu unordered_differs=%lu\n",
           TRIALS, invocations, ordered_ok, differ);
    return ordered_ok == TRIALS ? 0 : 3;
}
