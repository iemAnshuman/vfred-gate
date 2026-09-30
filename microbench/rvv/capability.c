// A bounded Linux userspace RVV 1.0 capability check; SIGILL stays in this process.
#include <stdio.h>
#include <stdint.h>
#include <signal.h>
#include <setjmp.h>
#include <riscv_vector.h>
static sigjmp_buf recovery;
static volatile sig_atomic_t stage=0;
static void unsupported(int signo){(void)signo;siglongjmp(recovery,1);}
int main(void){
    signal(SIGILL,unsupported);
    if(sigsetjmp(recovery,1)){
        printf("{\"rvv_1_0_probe\":\"unsupported_instruction\",\"execution_class\":\"hardware\",\"stage\":%d}\n",(int)stage);return 0;
    }
    stage=1;
    size_t vl=__riscv_vsetvl_e32m1(4);uintptr_t vtype=0;
    __asm__ volatile("csrr %0, vtype":"=r"(vtype));
    if(vl!=4 || (vtype>>63)){
        printf("{\"rvv_1_0_probe\":\"unsupported_vtype\",\"vl\":%lu,\"vtype\":%lu}\n",(unsigned long)vl,(unsigned long)vtype);return 0;
    }
    float data[4]={1,2,3,4};
    stage=2;
    vfloat32m1_t x=__riscv_vle32_v_f32m1(data,vl);
    vfloat32m1_t zero=__riscv_vfmv_v_f_f32m1(0,1);
    stage=3;
    float ordered=__riscv_vfmv_f_s_f32m1_f32(__riscv_vfredosum_vs_f32m1_f32m1(x,zero,vl));
    stage=4;
    float unordered=__riscv_vfmv_f_s_f32m1_f32(__riscv_vfredusum_vs_f32m1_f32m1(x,zero,vl));
    printf("{\"rvv_1_0_probe\":\"executed\",\"execution_class\":\"hardware\",\"vl\":%lu,\"vtype\":%lu,\"ordered\":%.1f,\"unordered\":%.1f}\n",(unsigned long)vl,(unsigned long)vtype,ordered,unordered);
    return ordered==10 && unordered==10?0:2;
}
