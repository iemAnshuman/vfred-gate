# Pinned runner API

The source lock selects llama.cpp commit
552f18f912a32ea86edf82e2b76431cb7131538d. The native probe was compiled and
executed on 1 October 2026.

The C++ adapter uses llama_model_load_from_file, llama_model_get_vocab,
llama_tokenize, llama_chat_apply_template, llama_init_from_model, llama_batch_init,
llama_decode and llama_get_logits_ith. Cleanup uses llama_batch_free, llama_free
and llama_model_free. The legacy batch interface is available at this pin.

Capture uses llama_context_params.cb_eval and ggml_backend_sched_eval_callback.
Query calls select observed nodes. Observation calls copy completed tensors
through ggml_backend_tensor_get. The diagnostic intervention uses
ggml_backend_tensor_set before dependent graph computation continues. Diagnostic
runs must observe the same nodes on both sides.

The observed SmolLM2 model has 49,152 vocabulary entries and 32 transformer
blocks. Layer output names include l_out-0 through l_out-31. These names were
observed from the graph, not copied from the synopsis.

CMake disables Metal, Accelerate, BLAS, CUDA, Vulkan, OpenMP, native tuning and
compiler caching. KV values and keys are explicitly float32. One token per batch
and one CPU worker are used for prefill and generation.

The recorded source patch prevents ggml from embedding this repository's HEAD
as the dependency version when building a source archive. It does not change
numerical kernels. Source revision and patch hash are recorded separately.

See runner/CMakeLists.txt and the generated build-manifest.json for the complete
effective build information. All timing from this instrumented runner is
diagnostic; it does not establish selective-hardening performance.

