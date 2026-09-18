#include "protocol.hpp"
#include <fstream>
#include <iostream>
int main(int argc,char**argv){
    try {
        if(argc!=3)throw std::runtime_error("usage: vfg-llama-runner REQUEST_JSON OUTPUT_DIRECTORY");
        fs::path out=argv[2];fs::create_directories(out);
        if(fs::exists(out/"result.json"))throw std::runtime_error("output already complete");
        std::ifstream f(argv[1]);if(!f)throw std::runtime_error("cannot read request");
        auto req=json::parse(f);
        if(req.at("schema_version")!=1)throw std::runtime_error("unsupported protocol version");
        if(file_digest(req.at("model_path").get<std::string>())!=req.at("model_sha256").get<std::string>())
            throw std::runtime_error("model hash mismatch");
        auto result=run_model(req,out);result["schema_version"]=1;result["complete"]=true;
        atomic_json(out/"result.json",result);
        std::cout<<"{\"complete\":true}\n";return 0;
    }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 4;}
}

