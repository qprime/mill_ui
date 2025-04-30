# cliff_ai/llm_server/model_runner.py
from transformers import AutoTokenizer, pipeline
from optimum.intel.openvino import OVModelForCausalLM

MODEL_PATH = "/home/squinlan/cliff_ai/models/mistral/quantized"

def load_model():
    model = OVModelForCausalLM.from_pretrained(MODEL_PATH, device="CPU")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    return pipeline("text-generation", model=model, tokenizer=tokenizer)

generator = load_model()

def run_generation(prompt: str, max_tokens: int = 200):
    result = generator(prompt, max_new_tokens=max_tokens)
    return result[0]["generated_text"]

