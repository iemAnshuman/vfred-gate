#include "protocol.hpp"
#include <fstream>
#include <stdexcept>
#include <array>
#include <cstring>
extern "C" {
#include "hash/sha256/sha256.h"
}
static std::string hex(const unsigned char *d) {
    const char *h="0123456789abcdef";std::string r;
    for(int i=0;i<32;++i){r+=h[d[i]>>4];r+=h[d[i]&15];}return r;
}
std::string digest(const void *p,size_t n) {
    unsigned char d[32];sha256_hash(d,static_cast<const unsigned char *>(p),n);return hex(d);
}
std::string file_digest(const fs::path &p) {
    std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("cannot open "+p.string());
    sha256_t ctx;sha256_init(&ctx);std::array<char,1048576>b{};
    while(f){f.read(b.data(),b.size());sha256_update(&ctx,reinterpret_cast<unsigned char *>(b.data()),static_cast<size_t>(f.gcount()));}
    if(!f.eof())throw std::runtime_error("error reading "+p.string());
    unsigned char d[32];sha256_final(&ctx,d);return hex(d);
}
std::string history_digest(const std::vector<int32_t>&tokens) {
    std::vector<unsigned char>b;for(auto t:tokens)for(int k=0;k<4;++k)b.push_back(static_cast<uint32_t>(t)>>(8*k));
    return digest(b.data(),b.size());
}
void atomic_json(const fs::path&p,const json&j) {
    auto tmp=p;tmp+=".tmp";std::ofstream f(tmp);f<<j.dump(2)<<"\n";f.close();
    if(!f)throw std::runtime_error("cannot write "+tmp.string());fs::rename(tmp,p);
}
void write_f32(std::ostream&f,const float*p,size_t n) {
    for(size_t i=0;i<n;++i){uint32_t u;std::memcpy(&u,p+i,4);char b[4];for(int k=0;k<4;++k)b[k]=u>>(8*k);f.write(b,4);}
    if(!f)throw std::runtime_error("cannot write float array");
}

