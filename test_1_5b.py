import os
import sys
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
if "tensorflow" not in sys.modules:
    sys.modules["tensorflow"] = None

from model import load_model, get_model_metadata, generate_with_xray_trace
from tokenizer import load_tokenizer, tokenize_text

print("Loading Qwen2.5-1.5B-Instruct...")
model, tokenizer, device = load_model("Qwen/Qwen2.5-1.5B-Instruct", device="cpu")
meta = get_model_metadata(model)
print("1.5B Metadata:", meta)

prompt = "Hello"
text, traces = generate_with_xray_trace(model, tokenizer, prompt=prompt, max_new_tokens=3)
print("1.5B Generated:", text)
print("1.5B Step traces count:", len(traces))
print("1.5B Verification SUCCESS!")

