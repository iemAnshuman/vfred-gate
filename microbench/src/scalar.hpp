#pragma once
#include <cstddef>
float left_fold(const float *, std::size_t, float seed = 0.0f);
float tree_sum(const float *, std::size_t);
double wide_sum(const float *, std::size_t);

