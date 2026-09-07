#include "scalar.hpp"
float left_fold(const float *x, std::size_t n, float seed) {
    float s = seed;
    for (std::size_t i=0; i<n; ++i) s = s + x[i];
    return s;
}
float tree_sum(const float *x, std::size_t n) {
    if (!n) return 0.0f;
    if (n==1) return x[0];
    const auto h=n/2;
    return tree_sum(x,h)+tree_sum(x+h,n-h);
}
double wide_sum(const float *x, std::size_t n) {
    double s=0;
    for (std::size_t i=0;i<n;++i) s+=static_cast<double>(x[i]);
    return s;
}

