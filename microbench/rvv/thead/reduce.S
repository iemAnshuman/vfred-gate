# Reductions for RVV 0.7.1 (XTheadVector) cores, hand-encoded because the
# available assemblers do not accept -march=rv64gc_xtheadvector.
# void vfg_thead_reduce(const float *x, size_t n, const float *zero, float *out, int ordered)
    .text
    .globl vfg_thead_reduce
vfg_thead_reduce:
    li t1, 1
    .word 0x008372d7  # th.vsetvli t0, t1, e32, m1
    .word 0x02067187  # th.vle.v v3, (a2)
1:
    beqz a1, 4f
    .word 0x0085f2d7  # th.vsetvli t0, a1, e32, m1
    .word 0x02057087  # th.vle.v v1, (a0)
    bnez a4, 2f
    .word 0x061191d7  # th.vfredsum.vs v3, v1, v3 (unordered)
    j 3f
2:
    .word 0x0e1191d7  # th.vfredosum.vs v3, v1, v3 (ordered)
3:
    slli t2, t0, 2
    add a0, a0, t2
    sub a1, a1, t0
    j 1b
4:
    li t1, 1
    .word 0x008372d7  # th.vsetvli t0, t1, e32, m1
    .word 0x0206f1a7  # th.vse.v v3, (a3)
    ret

# size_t vfg_thead_vlmax(size_t n): vl granted for n elements at e32, m1
    .globl vfg_thead_vlmax
vfg_thead_vlmax:
    .word 0x00857557  # th.vsetvli a0, a0, e32, m1
    ret
