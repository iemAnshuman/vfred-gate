#include <math.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
/* Exhaustive expf over every float in [-88, 0] (softmax inputs x - max are <= 0).
   Writes one FNV-1a hash per block of 4096 consecutive inputs; compare the files across systems. */
int main(int argc, char **argv){
  FILE *f = fopen(argv[1], "wb");
  uint32_t lo = 0x80000000u, hi = 0xC2B00000u; /* -0.0 .. -88.0 */
  for (uint32_t start = lo; start < hi; start += 4096) {
    uint64_t h = 1469598103934665603ULL;
    for (uint32_t u = start; u < start + 4096 && u < hi; u++) {
      float x, y; memcpy(&x, &u, 4); y = expf(x); uint32_t v; memcpy(&v, &y, 4);
      h ^= v; h *= 1099511628211ULL;
    }
    fwrite(&h, 8, 1, f);
  }
  fclose(f); return 0; }
