#include <math.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
/* ggml rope_yarn angles for SmolLM2-360M: n_dims=64, freq_base=100000, freq_scale=1, ext_factor=0.
   Same steps as ggml_rope_cache_init: theta=pos; theta*=theta_scale per pair. Writes theta,sin,cos. */
int main(int argc, char **argv){
  volatile float base = 100000.0f; volatile int n_dims = 64;
  float theta_scale = powf(base, -2.0f/n_dims);
  uint32_t ts; memcpy(&ts,&theta_scale,4); printf("theta_scale=%a bits=%08x\n",theta_scale,ts);
  FILE *f = fopen(argv[1],"wb");
  for(int pos=0;pos<512;pos++){ float theta=(float)pos;
    for(int i0=0;i0<64;i0+=2){ float v[3]={theta,sinf(theta),cosf(theta)}; fwrite(v,4,3,f); theta*=theta_scale; } }
  fclose(f); return 0; }
