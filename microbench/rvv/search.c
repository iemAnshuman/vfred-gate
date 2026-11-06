#include <riscv_vector.h>
#include <stdint.h>
#include <stddef.h>

static volatile unsigned char *uart = (unsigned char *)0x10000000;
static void put(char c) { while (!(uart[5] & 32)) {} uart[0] = (unsigned char)c; }
static void text(const char *s) { while (*s) put(*s++); }
static void number(uint64_t x) { char b[24]; unsigned n = 0; do { b[n++] = (char)('0' + x % 10); x /= 10; } while (x); while (n) put(b[--n]); }
static uint32_t bits(float x) { union { float f; uint32_t u; } v; v.f = x; return v.u; }
static uint64_t flags(void) { uint64_t v; __asm__ volatile("csrr %0, fflags" : "=r"(v)); return v; }

static uint64_t dynamic_ordered;
static uint64_t dynamic_unordered;
static uint64_t dynamic_ordered_chunks;
static uint64_t dynamic_unordered_chunks;

__attribute__((noinline)) float ordered(const float *x, size_t n) {
    vfloat32m1_t s = __riscv_vfmv_v_f_f32m1(0.0f, 1);
    for (size_t i = 0; i < n;) {
        size_t vl = __riscv_vsetvl_e32m1(n - i);
        vfloat32m1_t v = __riscv_vle32_v_f32m1(x + i, vl);
        s = __riscv_vfredosum_vs_f32m1_f32m1(v, s, vl);
        ++dynamic_ordered;
        ++dynamic_ordered_chunks;
        i += vl;
    }
    return __riscv_vfmv_f_s_f32m1_f32(s);
}

__attribute__((noinline)) float unordered(const float *x, size_t n) {
    vfloat32m1_t s = __riscv_vfmv_v_f_f32m1(0.0f, 1);
    for (size_t i = 0; i < n;) {
        size_t vl = __riscv_vsetvl_e32m1(n - i);
        vfloat32m1_t v = __riscv_vle32_v_f32m1(x + i, vl);
        s = __riscv_vfredusum_vs_f32m1_f32m1(v, s, vl);
        ++dynamic_unordered;
        ++dynamic_unordered_chunks;
        i += vl;
    }
    return __riscv_vfmv_f_s_f32m1_f32(s);
}

__attribute__((noinline)) float scalar(const float *x, size_t n) {
    float s = 0;
    for (size_t i = 0; i < n; ++i) s += x[i];
    return s;
}

static uint64_t state = 0x9e3779b97f4a7c15ULL;
static uint64_t random64(void) {
    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    return state;
}

static float random_value(void) {
    uint64_t r = random64();
    float m = 1.0f + (float)(r & 0x7fffff) * 0x1p-23f;
    int e = (int)((r >> 23) % 17) - 8;
    float v = m;
    if (e >= 0) for (int i = 0; i < e; ++i) v *= 2.0f;
    else for (int i = 0; i < -e; ++i) v *= 0.5f;
    return (r >> 40) & 1 ? -v : v;
}

static void emit_array(const float *x, size_t n) {
    put('[');
    for (size_t i = 0; i < n; ++i) {
        if (i) put(',');
        number(bits(x[i]));
    }
    put(']');
}

int main(void) {
    size_t vmax = __riscv_vsetvlmax_e32m1();
    uint64_t vlenb;
    __asm__ volatile("csrr %0, vlenb" : "=r"(vlenb));
    float x[128];
    uint64_t trials = 0;
    int found = 0;
    uint64_t found_trial = 0;
    size_t found_n = 0;
    float found_ordered = 0.0f, found_unordered = 0.0f, found_scalar = 0.0f;
    uint32_t found_ordered_bits = 0, found_unordered_bits = 0, found_scalar_bits = 0;
    uint64_t found_ordered_fflags = 0, found_unordered_fflags = 0;
    enum { SAMPLE_COUNT = 24 };
    float sample_x[SAMPLE_COUNT][64];
    size_t sample_n[SAMPLE_COUNT];
    uint32_t sample_ordered[SAMPLE_COUNT], sample_unordered[SAMPLE_COUNT], sample_scalar[SAMPLE_COUNT];
    size_t samples = 0;

    for (uint64_t trial = 0; trial < 20000 && !found; ++trial) {
        size_t n = 2 + (size_t)(random64() % 31);
        for (size_t i = 0; i < n; ++i) x[i] = random_value();
        ++trials;
        __asm__ volatile("csrwi fflags, 0");
        float a = ordered(x, n);
        uint64_t af = flags();
        __asm__ volatile("csrwi fflags, 0");
        float b = unordered(x, n);
        uint64_t bf = flags();
        float c = scalar(x, n);
        if (bits(a) != bits(c)) continue;
        if (samples < SAMPLE_COUNT) {
            sample_n[samples] = n;
            for (size_t i = 0; i < n; ++i) sample_x[samples][i] = x[i];
            sample_ordered[samples] = bits(a);
            sample_unordered[samples] = bits(b);
            sample_scalar[samples] = bits(c);
            ++samples;
        }
        if (bits(a) != bits(b)) {
            found = 1;
            found_trial = trial;
            found_n = n;
            found_ordered = a;
            found_unordered = b;
            found_scalar = c;
            found_ordered_bits = bits(a);
            found_unordered_bits = bits(b);
            found_scalar_bits = bits(c);
            found_ordered_fflags = af;
            found_unordered_fflags = bf;
            break;
        }
    }

    text("{\"schema_version\":1,\"execution_class\":\"emulator\",\"vlen_bits\":");
    number(vlenb * 8);
    text(",\"vlmax\":");
    number(vmax);
    text(",\"sew\":32,\"lmul\":1,\"frm\":0,\"mask\":\"unmasked\",\"seed_bits\":0");
    text(",\"search\":{\"algorithm\":\"xorshift64\",\"seed\":");
    number(0x9e3779b97f4a7c15ULL);
    text(",\"trials\":");
    number(trials);
    text(",\"max_trials\":20000,\"length_range\":[2,32]");
    text(",\"exponent_range\":[-8,8]}");
    text(",\"found\":");
    text(found ? "true" : "false");
    text(",\"found_trial\":");
    number(found_trial);
    text(",\"n\":");
    number(found_n);
    text(",\"input_bits\":");
    if (found) emit_array(x, found_n); else text("[]");
    text(",\"ordered_bits\":");
    number(found_ordered_bits);
    text(",\"unordered_bits\":");
    number(found_unordered_bits);
    text(",\"scalar_bits\":");
    number(found_scalar_bits);
    text(",\"ordered_fflags\":");
    number(found_ordered_fflags);
    text(",\"unordered_fflags\":");
    number(found_unordered_fflags);
    text(",\"ordered_matches_scalar\":");
    text(found && found_ordered_bits == found_scalar_bits ? "true" : "false");
    text(",\"samples\":[");
    for (size_t s = 0; s < samples; ++s) {
        if (s) put(',');
        text("{\"trial\":");
        number(s);
        text(",\"n\":");
        number(sample_n[s]);
        text(",\"input_bits\":");
        emit_array(sample_x[s], sample_n[s]);
        text(",\"ordered_bits\":");
        number(sample_ordered[s]);
        text(",\"unordered_bits\":");
        number(sample_unordered[s]);
        text(",\"scalar_bits\":");
        number(sample_scalar[s]);
        put('}');
    }
    text("],\"dynamic\":{\"ordered_invocations\":");
    number(dynamic_ordered);
    text(",\"unordered_invocations\":");
    number(dynamic_unordered);
    text(",\"ordered_chunks\":");
    number(dynamic_ordered_chunks);
    text(",\"unordered_chunks\":");
    number(dynamic_unordered_chunks);
    text("}}\n");
    return found ? 0 : 2;
}
