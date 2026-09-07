#include "scalar.hpp"
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>
static uint32_t bits(float x) { uint32_t u; std::memcpy(&u,&x,4); return u; }
int main(int argc,char **argv) {
    std::vector<std::pair<std::string,std::vector<float>>> fixtures={
      {"exact",{1,2,3,4}},
      {"cancellation",{16777216.0f,1.0f,-16777216.0f,1.0f}},
      {"absorption",{16777216.0f,1.0f,1.0f,1.0f}},
      {"empty",{}}, {"single",{3.25f}}, {"signed_zero",{-0.0f,0.0f}}
    };
    uint32_t state=42;
    std::vector<float> values;
    for(int i=0;i<4099;++i) {
      state^=state<<13; state^=state>>17; state^=state<<5;
      values.push_back(static_cast<float>(state>>8)*0x1p-24f);
    }
    fixtures.push_back({"xorshift32_42",values});
    bool ok=left_fold(fixtures[0].second.data(),4)==10.0f &&
      left_fold(fixtures[1].second.data(),4)==1.0f &&
      tree_sum(fixtures[1].second.data(),4)==1.0f &&
      wide_sum(fixtures[1].second.data(),4)==2.0 &&
      left_fold(fixtures[2].second.data(),4)!=tree_sum(fixtures[2].second.data(),4);
    const bool self=argc==2 && std::string(argv[1])=="--self-test";
    if(self) { std::cout << (ok ? "reduction references passed\n" : "reduction references failed\n"); return ok ? 0 : 1; }
    std::cout << "{\"schema_version\":1,\"execution_class\":\"host\",\"self_test\":"
              << (ok?"true":"false") << ",\"fixtures\":[";
    bool first=true;
    for(const auto &f:fixtures) {
      if(!first) std::cout<<",";
      first=false;
      const auto &x=f.second;
      std::cout<<"{\"id\":\""<<f.first<<"\",\"n\":"<<x.size()<<",\"input_bits\":[";
      for(std::size_t i=0;i<x.size();++i) { if(i)std::cout<<",";std::cout<<bits(x[i]); }
      std::cout<<"],\"left_bits\":"<<bits(left_fold(x.data(),x.size()))
        <<",\"tree_bits\":"<<bits(tree_sum(x.data(),x.size()))
        <<",\"wide\":"<<std::setprecision(17)<<wide_sum(x.data(),x.size())<<"}";
    }
    std::cout<<"]}\n";
    return self && !ok ? 1:0;
}
