#include <riscv_vector.h>
#include <stdint.h>
#include <stddef.h>
static volatile unsigned char *uart=(unsigned char *)0x10000000;
static void put(char c) { while(!(uart[5]&32)){} uart[0]=(unsigned char)c; }
static void text(const char *s) { while(*s) put(*s++); }
static void number(uint64_t x) { char b[24]; unsigned n=0; do {b[n++]=(char)('0'+x%10);x/=10;}while(x);while(n)put(b[--n]); }
static uint32_t bits(float x) { union {float f;uint32_t u;} v;v.f=x;return v.u; }
static uint64_t flags(void) { uint64_t v;__asm__ volatile("csrr %0, fflags":"=r"(v));return v; }
__attribute__((noinline)) float ordered(const float *x,size_t n) {
    vfloat32m1_t s=__riscv_vfmv_v_f_f32m1(0.0f,1);
    for(size_t i=0;i<n;) {
        size_t vl=__riscv_vsetvl_e32m1(n-i);
        vfloat32m1_t v=__riscv_vle32_v_f32m1(x+i,vl);
        s=__riscv_vfredosum_vs_f32m1_f32m1(v,s,vl);i+=vl;
    }
    return __riscv_vfmv_f_s_f32m1_f32(s);
}
__attribute__((noinline)) float unordered(const float *x,size_t n) {
    vfloat32m1_t s=__riscv_vfmv_v_f_f32m1(0.0f,1);
    for(size_t i=0;i<n;) {
        size_t vl=__riscv_vsetvl_e32m1(n-i);
        vfloat32m1_t v=__riscv_vle32_v_f32m1(x+i,vl);
        s=__riscv_vfredusum_vs_f32m1_f32m1(v,s,vl);i+=vl;
    }
    return __riscv_vfmv_f_s_f32m1_f32(s);
}
__attribute__((noinline)) float scalar(const float *x,size_t n) { float s=0;for(size_t i=0;i<n;++i)s+=x[i];return s; }
int main(void) {
    size_t vmax=__riscv_vsetvlmax_e32m1();
    uint64_t vlenb;__asm__ volatile("csrr %0, vlenb":"=r"(vlenb));
    size_t lengths[]={0,1,vmax-1,vmax,vmax+1,2*vmax+3,4};
    text("{\"schema_version\":1,\"execution_class\":\"emulator\",\"vlen_bits\":");number(vlenb*8);
    text(",\"vlmax\":");number(vmax);text(",\"sew\":32,\"lmul\":1,\"frm\":0,\"mask\":\"unmasked\",\"seed_bits\":0,\"records\":[");
    int first=1,ok=1;
    float x[4096];
    if(vmax*2+3>4096) return 1;
    for(unsigned fixture=0;fixture<4;++fixture)for(unsigned k=0;k<7;++k) {
        size_t n=lengths[k];
        for(size_t i=0;i<n;++i) {
            if(fixture==0)x[i]=(float)(i+1);
            else if(fixture==1)x[i]=i==0?16777216.0f:1.0f;
            else if(fixture==2)x[i]=(i%4==0?16777216.0f:(i%4==2?-16777216.0f:1.0f));
            else x[i]=(i%2)?0.0f:-0.0f;
        }
        for(unsigned rep=0;rep<5;++rep) {
            __asm__ volatile("csrwi fflags, 0");
            float a=ordered(x,n);uint64_t af=flags();
            __asm__ volatile("csrwi fflags, 0");
            float b=unordered(x,n);uint64_t bf=flags();
            float c=scalar(x,n);
            if(bits(a)!=bits(c))ok=0;
            if(!first)put(',');first=0;
            text("{\"fixture\":");number(fixture);text(",\"n\":");number(n);
            text(",\"repetition\":");number(rep);text(",\"ordered_bits\":");number(bits(a));
            text(",\"unordered_bits\":");number(bits(b));text(",\"scalar_bits\":");number(bits(c));
            text(",\"ordered_fflags\":");number(af);text(",\"unordered_fflags\":");number(bf);
            text(",\"input_bits\":[");for(size_t i=0;i<n;++i){if(i)put(',');number(bits(x[i]));}
            text("],\"chunks\":[");
            for(size_t i=0;i<n;) {
                if(i)put(',');
                size_t vl=__riscv_vsetvl_e32m1(n-i);
                uint64_t vt;__asm__ volatile("csrr %0, vtype":"=r"(vt));
                text("{\"offset\":");number(i);text(",\"vl\":");number(vl);text(",\"vtype\":");number(vt);put('}');
                i+=vl;
            }
            text("]}");
        }
    }
    text("],\"ordered_matches_scalar\":");text(ok?"true":"false");text("}\n");
    return 0;
}

