#pragma once
#include <nlohmann/json.hpp>
#include <filesystem>
#include <vector>
#include <string>
#include <cstdint>
using json=nlohmann::ordered_json;
namespace fs=std::filesystem;
std::string digest(const void *,size_t);
std::string file_digest(const fs::path &);
std::string history_digest(const std::vector<int32_t> &);
void atomic_json(const fs::path &,const json &);
void write_f32(std::ostream &,const float *,size_t);
json run_model(const json &, const fs::path &);

