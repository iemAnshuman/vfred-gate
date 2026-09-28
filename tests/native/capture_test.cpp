// Compile the production callback into this test TU to exercise strided views.
#include "../../runner/src/model_session.cpp"
#include "ggml-alloc.h"
#include "ggml-cpu.h"
int main(int argc,char**argv){
    if(argc!=2)return 2;
    fs::path out=argv[1];fs::create_directories(out);
    ggml_init_params params{1024*1024,nullptr,true};
    auto*ctx=ggml_init(params);
    auto*base=ggml_new_tensor_2d(ctx,GGML_TYPE_F32,8,3);
    auto*view=ggml_view_2d(ctx,base,4,3,8*sizeof(float),0);
    view->op=GGML_OP_ADD;ggml_set_name(view,"strided-fixture");
    auto*buffer=ggml_backend_alloc_ctx_tensors_from_buft(ctx,ggml_backend_cpu_buffer_type());
    float values[24];for(int i=0;i<24;++i)values[i]=float(i);
    ggml_backend_tensor_set(base,values,0,sizeof(values));
    Capture capture;capture.config={{"mode","all"},{"payloads",true}};capture.out=out;
    capture.history=history_digest({1});capture.stream.open(out/"captures.jsonl");
    if(!capture.observe(view))return 3;
    for(int row=0;row<3;++row)for(int col=4;col<8;++col)values[row*8+col]=-999;
    ggml_backend_tensor_set(base,values,0,sizeof(values));
    if(!capture.observe(view))return 4;
    capture.stream.close();
    auto a=out/"tensor-0.f32",b=out/"tensor-1.f32";
    if(fs::file_size(a)!=12*4||file_digest(a)!=file_digest(b))return 5;
    std::ifstream f(a,std::ios::binary);float actual[12];f.read(reinterpret_cast<char*>(actual),sizeof(actual));
    for(int row=0;row<3;++row)for(int col=0;col<4;++col)if(actual[row*4+col]!=float(row*8+col))return 6;
    ggml_backend_buffer_free(buffer);ggml_free(ctx);
    std::cout<<"strided capture excludes padding and preserves logical order\n";return 0;
}
