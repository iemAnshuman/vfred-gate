#include "protocol.hpp"
#include "llama.h"
#include "ggml.h"
#include "ggml-backend.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <sstream>
#include <stdexcept>
using Clock=std::chrono::steady_clock;
static double seconds(Clock::time_point t){return std::chrono::duration<double>(Clock::now()-t).count();}
static void log_message(enum ggml_log_level,const char*text,void*){std::cerr<<text;}
struct Capture {
    json config,injection;fs::path out;std::ofstream stream;
    int position=0,step=0;size_t ordinal=0;std::string history,error;
    int injections=0;
    bool selected(ggml_tensor*t)const{
        if(t->type!=GGML_TYPE_F32 || t->op==GGML_OP_NONE)return false;
        std::string name=t->name,mode=config.value("mode","none");
        if(!injection.empty() && name==injection.value("tensor",""))return true;
        if(mode=="none")return false;
        auto match=config.value("match",std::string());
        if(!match.empty())return name.find(match)!=std::string::npos;
        if(mode=="layer")return name.find("l_out-")!=std::string::npos || name=="result_output" || name.find("result_norm")!=std::string::npos;
        return true;
    }
    bool observe(ggml_tensor*t){
        try{
            std::vector<uint8_t>raw(ggml_nbytes(t));ggml_backend_tensor_get(t,raw.data(),0,raw.size());
            bool injected=false;
            if(!injection.empty() && std::string(t->name)==injection.value("tensor","") &&
               position==injection.value("position",-1)){
                if(!ggml_is_contiguous(t))throw std::runtime_error("injection requires contiguous f32");
                auto index=injection.value("element",0);
                if(index<0 || static_cast<size_t>(index)>=ggml_nelements(t))throw std::runtime_error("injection element out of range");
                float v;std::memcpy(&v,raw.data()+4*index,4);v+=injection.at("delta").get<float>();
                if(!std::isfinite(v))throw std::runtime_error("non-finite injection");
                std::memcpy(raw.data()+4*index,&v,4);ggml_backend_tensor_set(t,raw.data(),0,raw.size());
                injected=true;++injections;
            }
            std::vector<float>logical;logical.reserve(ggml_nelements(t));
            for(int64_t i3=0;i3<t->ne[3];++i3)for(int64_t i2=0;i2<t->ne[2];++i2)
             for(int64_t i1=0;i1<t->ne[1];++i1)for(int64_t i0=0;i0<t->ne[0];++i0){
                size_t offset=i0*t->nb[0]+i1*t->nb[1]+i2*t->nb[2]+i3*t->nb[3];
                if(offset+4>raw.size())throw std::runtime_error("tensor stride outside allocation");
                float v;std::memcpy(&v,raw.data()+offset,4);logical.push_back(v);
             }
            // Canonical little-endian float payload excludes allocation padding.
            std::ostringstream bytes(std::ios::out|std::ios::binary);write_f32(bytes,logical.data(),logical.size());
            auto b=bytes.str();
            json event={{"position",position},{"prediction_step",step},{"ordinal",ordinal++},
              {"history_sha256",history},{"name",t->name},{"op",ggml_op_name(t->op)},
              {"shape",{t->ne[0],t->ne[1],t->ne[2],t->ne[3]}},{"dtype","<f4"},
              {"strides",{t->nb[0],t->nb[1],t->nb[2],t->nb[3]}},{"sha256",digest(b.data(),b.size())},
              {"injected",injected}};
            if(config.value("payloads",false)){
                std::string name="tensor-"+std::to_string(event["ordinal"].get<size_t>())+".f32";
                std::ofstream f(out/name,std::ios::binary);f.write(b.data(),b.size());f.close();
                if(!f)throw std::runtime_error("capture write failed");event["payload"]=name;
            }
            stream<<event.dump()<<"\n";if(!stream)throw std::runtime_error("capture index write failed");
            return true;
        }catch(const std::exception&e){error=e.what();return false;}
    }
};
static bool callback(ggml_tensor*t,bool ask,void*p){auto*c=static_cast<Capture*>(p);return ask?c->selected(t):c->observe(t);}
static std::vector<int32_t> tokenize(const llama_vocab*v,const std::string&s){
    int n=llama_tokenize(v,s.data(),s.size(),nullptr,0,true,true);
    if(n>=0)throw std::runtime_error("unexpected tokenization probe");
    std::vector<int32_t>tokens(-n);int got=llama_tokenize(v,s.data(),s.size(),tokens.data(),tokens.size(),true,true);
    if(got<0)throw std::runtime_error("tokenization failed");tokens.resize(got);return tokens;
}
json run_model(const json&req,const fs::path&out){
    llama_log_set(log_message,nullptr);llama_backend_init();
    auto load_start=Clock::now();
    auto mp=llama_model_default_params();mp.n_gpu_layers=0;
    mp.vocab_only=req.value("mode","free_run")=="tokenize";
    std::unique_ptr<llama_model,decltype(&llama_model_free)>model(
        llama_model_load_from_file(req.at("model_path").get<std::string>().c_str(),mp),llama_model_free);
    if(!model)throw std::runtime_error("model load failed");
    double load_seconds=seconds(load_start);
    const auto*vocab=llama_model_get_vocab(model.get());int nv=llama_vocab_n_tokens(vocab);
    const char*tmpl=llama_model_chat_template(model.get(),nullptr);
    std::string template_text=tmpl?tmpl:"";
    json info={{"vocab_size",nv},{"chat_template",template_text},{"chat_template_sha256",digest(template_text.data(),template_text.size())},
      {"model_sha256",req.at("model_sha256")},{"backend","cpu"},{"diagnostic_build",true}};
    if(req.value("mode","free_run")=="tokenize"){
        json cases=json::array();
        for(const auto&item:req.at("texts")){
            std::string content=item.at("text"),formatted=content;
            if(req.value("apply_chat_template",true)){
                if(template_text.empty())throw std::runtime_error("model has no chat template");
                llama_chat_message message={"user",content.c_str()};
                std::vector<char>b(content.size()+4096);
                int n=llama_chat_apply_template(template_text.c_str(),&message,1,true,b.data(),b.size());
                if(n<0)throw std::runtime_error("chat template unsupported");
                if(static_cast<size_t>(n)>b.size()){b.resize(n+1);n=llama_chat_apply_template(template_text.c_str(),&message,1,true,b.data(),b.size());}
                formatted.assign(b.data(),n);
            }
            cases.push_back({{"id",item.at("id")},{"tokens",tokenize(vocab,formatted)},
              {"formatted_text_sha256",digest(formatted.data(),formatted.size())}});
        }
        return {{"model",info},{"cases",cases},{"load_seconds",load_seconds}};
    }
    auto prompt=req.at("prompt_tokens").get<std::vector<int32_t>>();
    auto forced=req.value("forced_tokens",std::vector<int32_t>{});
    bool teacher=req.value("mode","free_run")=="teacher_forced";
    int max_tokens=req.value("max_tokens",32),nctx=req.value("context",512);
    if(prompt.empty()||max_tokens<1||nctx<1||prompt.size()+max_tokens>static_cast<size_t>(nctx))
        throw std::runtime_error("empty prompt or context overflow");
    if(teacher && forced.size()<static_cast<size_t>(max_tokens-1))throw std::runtime_error("forced history is too short");
    for(auto token:prompt)if(token<0||token>=nv)throw std::runtime_error("invalid prompt token");
    for(auto token:forced)if(token<0||token>=nv)throw std::runtime_error("invalid forced token");
    Capture capture;capture.config=req.value("capture",json::object());capture.injection=req.value("injection",json::object());capture.out=out;
    capture.stream.open(out/"captures.jsonl");
    auto cp=llama_context_default_params();cp.n_ctx=nctx;cp.n_batch=1;cp.n_ubatch=1;cp.n_seq_max=1;
    cp.n_threads=1;cp.n_threads_batch=1;cp.type_k=GGML_TYPE_F32;cp.type_v=GGML_TYPE_F32;
    cp.offload_kqv=false;cp.op_offload=false;cp.flash_attn_type=LLAMA_FLASH_ATTN_TYPE_DISABLED;
    if(capture.config.value("mode","none")!="none"||!capture.injection.empty()){cp.cb_eval=callback;cp.cb_eval_user_data=&capture;}
    std::unique_ptr<llama_context,decltype(&llama_free)>ctx(llama_init_from_model(model.get(),cp),llama_free);
    if(!ctx)throw std::runtime_error("context creation failed");
    auto batch=llama_batch_init(1,0,1);
    struct BatchGuard { llama_batch*b;~BatchGuard(){llama_batch_free(*b);} } guard{&batch};
    std::vector<int32_t>history;
    auto ingest=[&](int32_t token){
        int pos=history.size();history.push_back(token);
        capture.position=pos;capture.step=pos+1-static_cast<int>(prompt.size());capture.history=history_digest(history);
        batch.n_tokens=1;batch.token[0]=token;batch.pos[0]=pos;batch.n_seq_id[0]=1;batch.seq_id[0][0]=0;batch.logits[0]=1;
        int rc=llama_decode(ctx.get(),batch);
        if(rc!=0)throw std::runtime_error("decode failed ("+std::to_string(rc)+"): "+capture.error);
    };
    auto prefill_start=Clock::now();for(auto t:prompt)ingest(t);double prefill_seconds=seconds(prefill_start);
    std::ofstream logits_file(out/"logits.f32",std::ios::binary),events(out/"events.jsonl");
    auto generation_start=Clock::now();json steps=json::array();std::vector<int32_t>selected;
    std::string stop="token_budget";bool finite=true;
    for(int step=0;step<max_tokens;++step){
        float*ptr=llama_get_logits_ith(ctx.get(),-1);if(!ptr)throw std::runtime_error("no logits");
        std::vector<float>logits(ptr,ptr+nv);
        for(float x:logits)if(!std::isfinite(x))finite=false;
        if(!finite)throw std::runtime_error("non-finite logits");
        int winner=0;for(int i=1;i<nv;++i)if(logits[i]>logits[winner])winner=i;
        selected.push_back(winner);write_f32(logits_file,logits.data(),logits.size());
        json event={{"step",step},{"history_sha256",history_digest(history)},{"selected_token",winner},
                    {"offset_bytes",static_cast<uint64_t>(step)*nv*4},{"shape",{nv}},{"dtype","<f4"}};
        steps.push_back(event);events<<event.dump()<<"\n";
        if(!teacher && llama_vocab_is_eog(vocab,winner)){stop="eos";break;}
        if(step+1<max_tokens)ingest(teacher?forced[step]:winner);
    }
    double generation_seconds=seconds(generation_start);
    logits_file.close();events.close();capture.stream.close();
    if(!logits_file||!events||!capture.stream)throw std::runtime_error("output flush failed");
    if(!capture.injection.empty()&&capture.injections!=1)throw std::runtime_error("injection did not hit exactly once");
    return {{"model",info},{"case_id",req.at("case_id")},{"mode",teacher?"teacher_forced":"free_run"},
      {"prompt_tokens",prompt},{"forced_tokens",forced},{"selected_tokens",selected},{"stop_reason",stop},
      {"steps",steps},{"logits_file","logits.f32"},{"logits_sha256",file_digest(out/"logits.f32")},
      {"logits_shape",{steps.size(),nv}},{"injection_count",capture.injections},
      {"load_seconds",load_seconds},{"prefill_seconds",prefill_seconds},{"generation_seconds",generation_seconds},
      {"capture_events",capture.ordinal},{"context",nctx},{"threads",1},{"kv_type","f32"}};
}
