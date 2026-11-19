import sys
import os

# Prevent slow TensorFlow detection during Transformers import
if "tensorflow" not in sys.modules:
    sys.modules["tensorflow"] = None

os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

try:
    import transformers.utils.import_utils as _import_utils
    _import_utils.is_tf_available = lambda: False
    _import_utils.is_tf_text_available = lambda: False
except Exception:
    pass

import numpy as np
import torch
import torch.nn.functional as F
from typing import Dict, Any, List, Tuple, Optional
from transformers import AutoModelForCausalLM, AutoTokenizer


from tokenizer import resolve_local_model_path


def get_device() -> torch.device:
    """Returns the best available torch device."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_model(
    model_name: str = "Qwen/Qwen2.5-1.5B-Instruct",
    device: Optional[str] = None
) -> Tuple[AutoModelForCausalLM, AutoTokenizer, torch.device]:
    """
    Loads Hugging Face CausalLM model and Tokenizer with fast local caching and multi-thread optimization.
    
    Args:
        model_name: HF model path or identifier
        device: 'cuda', 'cpu', or auto-detected
    """
    target_device = get_device() if device is None else torch.device(device)
    target_path = resolve_local_model_path(model_name)

    # Utilize all CPU cores for multi-threaded math ops
    if target_device.type == "cpu":
        avail_threads = os.cpu_count() or 4
        torch.set_num_threads(avail_threads)

    # Fast tokenizer loading: query local cache first to avoid slow Hub network requests
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            target_path,
            local_files_only=True,
            trust_remote_code=True
        )
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(
            target_path,
            trust_remote_code=True
        )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Use native bfloat16 for instant loading (0.15s) and 50% lower RAM footprint.
    # Qwen safetensors are saved natively in bfloat16; converting to float32 on CPU takes 20-40s.
    torch_dtype = torch.bfloat16

    # Load model: try local files first with eager attention for attention-head inspection
    model = None
    for local_only in [True, False]:
        try:
            model = AutoModelForCausalLM.from_pretrained(
                target_path,
                dtype=torch_dtype,
                attn_implementation="eager",
                trust_remote_code=True,
                low_cpu_mem_usage=True,
                local_files_only=local_only
            )
            break
        except Exception:
            try:
                model = AutoModelForCausalLM.from_pretrained(
                    target_path,
                    dtype=torch_dtype,
                    trust_remote_code=True,
                    low_cpu_mem_usage=True,
                    local_files_only=local_only
                )
                break
            except Exception:
                continue

    if model is None:
        # Ultimate fallback
        model = AutoModelForCausalLM.from_pretrained(
            target_path,
            dtype=torch_dtype,
            trust_remote_code=True,
            low_cpu_mem_usage=True
        )

    if target_device.type != "cpu":
        model.to(target_device)
    model.eval()

    # Ensure eager attention is active for output_attentions support
    try:
        model.set_attn_implementation("eager")
    except Exception:
        pass

    return model, tokenizer, target_device


def get_model_metadata(model: AutoModelForCausalLM) -> Dict[str, Any]:
    """Returns architecture specifications of the model."""
    config = model.config
    
    num_layers = getattr(config, "num_hidden_layers", getattr(config, "n_layer", 28))
    hidden_dim = getattr(config, "hidden_size", getattr(config, "n_embd", 1536))
    num_heads = getattr(config, "num_attention_heads", getattr(config, "n_head", 12))
    vocab_size = getattr(config, "vocab_size", 151643)
    num_kv_heads = getattr(config, "num_key_value_heads", num_heads)
    intermediate_dim = getattr(config, "intermediate_size", 4864)
    
    # Calculate parameter count in billions
    total_params = sum(p.numel() for p in model.parameters())
    params_b = round(total_params / 1e9, 2)
    params_fmt = f"{params_b:.2f}B" if params_b >= 1.0 else f"{round(total_params / 1e6)}M ({params_b:.2f}B)"
    
    return {
        "model_type": getattr(config, "model_type", "qwen2"),
        "num_layers": num_layers,
        "hidden_dim": hidden_dim,
        "num_heads": num_heads,
        "num_kv_heads": num_kv_heads,
        "intermediate_dim": intermediate_dim,
        "vocab_size": vocab_size,
        "total_params": total_params,
        "total_params_b": params_b,
        "num_parameters_formatted": params_fmt,
        "device": next(model.parameters()).device.type
    }


def extract_embeddings(
    model: AutoModelForCausalLM,
    input_ids: List[int]
) -> Dict[str, Any]:
    """
    Extracts raw token input embeddings and summary metrics.
    
    Returns:
    - embedding_matrix: (seq_len, hidden_dim) numpy array
    - stats: list of dicts per token (norm, mean, std, min, max, first 10 values)
    """
    embed_layer = model.get_input_embeddings()
    device = next(model.parameters()).device
    
    tensor_ids = torch.tensor([input_ids], device=device, dtype=torch.long)
    with torch.inference_mode():
        embeddings = embed_layer(tensor_ids)[0]  # (seq_len, hidden_dim)

    embed_np = embeddings.cpu().float().numpy()
    seq_len, embed_dim = embed_np.shape

    # Vectorized L2 norm for all tokens at once
    norms = np.linalg.norm(embed_np, axis=1)

    stats = []
    for i in range(seq_len):
        vec = embed_np[i]
        stats.append({
            "token_index": i,
            "token_id": input_ids[i],
            "norm": round(float(norms[i]), 4),
            "mean": round(float(vec.mean()), 4),
            "std": round(float(vec.std()), 4),
            "min": round(float(vec.min()), 4),
            "max": round(float(vec.max()), 4),
            "slice": [round(float(v), 4) for v in vec[:10]]
        })

    return {
        "embedding_matrix": embed_np,
        "embed_dim": embed_dim,
        "stats": stats
    }


def forward_xray(
    model: AutoModelForCausalLM,
    input_ids: List[int]
) -> Dict[str, Any]:
    """
    Executes a full model forward pass with output_attentions=True and output_hidden_states=True.
    
    Returns:
    - attentions: List of attention matrices per layer [layer_idx] -> numpy (num_heads, seq_len, seq_len)
    - hidden_states: List of hidden state matrices per layer [layer_idx] -> numpy (seq_len, hidden_dim)
    - last_logits: Numpy vector (vocab_size) for the last token position
    """
    device = next(model.parameters()).device
    tensor_ids = torch.tensor([input_ids], device=device, dtype=torch.long)

    with torch.inference_mode():
        outputs = model(
            input_ids=tensor_ids,
            output_attentions=True,
            output_hidden_states=True,
            return_dict=True
        )

    # attentions: tuple of (1, num_heads, seq_len, seq_len) per layer
    attentions_list = [att[0].cpu().float().numpy() for att in outputs.attentions]

    # hidden_states: tuple of (1, seq_len, hidden_dim) — layer 0 is embeddings
    hidden_states_list = [hs[0].cpu().float().numpy() for hs in outputs.hidden_states]

    # Logits for the last token position
    logits = outputs.logits[0, -1, :].cpu().float().numpy()

    return {
        "attentions": attentions_list,
        "hidden_states": hidden_states_list,
        "last_logits": logits
    }


def compute_logits_and_probs(
    logits: torch.Tensor,
    tokenizer: AutoTokenizer,
    top_k: int = 10,
    temperature: float = 1.0,
    top_p: float = 1.0
) -> List[Dict[str, Any]]:
    """
    Applies Temperature scaling, Softmax, and extracts Top-K predicted tokens.
    
    Returns list of top predictions with:
    - token_id
    - token_str
    - logit
    - probability (0.0 to 1.0)
    - percentage (e.g. 32.5%)
    """
    if isinstance(logits, list) or hasattr(logits, "__array__"):
        logits = torch.as_tensor(logits, dtype=torch.float32)
    else:
        logits = logits.float()
        
    # Temperature scaling
    temp = max(temperature, 0.01)
    scaled_logits = logits / temp
    
    # Softmax probabilities
    probs = F.softmax(scaled_logits, dim=-1)
    
    # Fast Top-P filtering: pre-select top 200 candidates to avoid sorting all 151k vocab items on CPU
    if top_p < 1.0:
        cand_k = min(200, probs.size(-1))
        cand_probs, cand_indices = torch.topk(probs, k=cand_k)
        cumulative_probs = torch.cumsum(cand_probs, dim=-1)
        keep_mask = cumulative_probs <= top_p
        keep_mask[0] = True
        
        selected_indices = cand_indices[keep_mask][:top_k]
        selected_probs = cand_probs[keep_mask][:top_k]
    else:
        selected_probs, selected_indices = torch.topk(probs, k=min(top_k, len(probs)))
    
    predictions = []
    for rank in range(len(selected_indices)):
        tid = int(selected_indices[rank].item())
        prob = float(selected_probs[rank].item())
        raw_logit = float(logits[tid].item())
        tok_str = tokenizer.decode([tid])
        
        # Format display string
        display_str = tok_str
        if display_str == " ":
            display_str = "␣ (space)"
        elif display_str == "\n":
            display_str = "↵ (newline)"
            
        predictions.append({
            "rank": rank + 1,
            "token_id": tid,
            "token_str": tok_str,
            "display_str": display_str,
            "logit": round(raw_logit, 4),
            "probability": prob,
            "percentage": round(prob * 100, 2)
        })
        
    return predictions


def generate_with_xray_trace(
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    prompt: str,
    max_new_tokens: int = 20,
    temperature: float = 0.7,
    top_k: int = 50,
    top_p: float = 0.9,
    step_callback: Optional[Any] = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Generates text while capturing step-by-step token trace and probability distributions.
    Optimized with KV Cache (past_key_values) for fast per-token generation.
    
    Returns:
    - full_response_text: string of generated completion
    - step_traces: list of dicts for each generated step containing top candidates & selected token
    """
    device = next(model.parameters()).device
    
    # Format prompt using chat template if available, or direct encode
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful, knowledgeable AI assistant. Provide complete, detailed, "
                    "and comprehensive answers with clear explanations. Write in full, articulate sentences "
                    "and ensure all explanations are properly concluded."
                )
            },
            {"role": "user", "content": prompt}
        ]
        try:
            formatted_prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            formatted_prompt = prompt
    else:
        formatted_prompt = prompt

    input_ids = tokenizer.encode(formatted_prompt, return_tensors="pt").to(device)

    step_traces = []
    generated_token_ids = []
    past_key_values = None
    chosen_id = None

    with torch.inference_mode():
        # Initial prompt prefill with KV caching enabled
        outputs = model(input_ids, use_cache=True, return_dict=True)
        past_key_values = outputs.past_key_values
        next_token_logits = outputs.logits[0, -1, :].clone()

        for step in range(max_new_tokens):
            if step > 0:
                # Fast single-token forward pass using cached keys and values
                cur_input = torch.tensor([[chosen_id]], device=device, dtype=torch.long)
                outputs = model(cur_input, past_key_values=past_key_values, use_cache=True, return_dict=True)
                past_key_values = outputs.past_key_values
                next_token_logits = outputs.logits[0, -1, :].clone()

            # Extract top candidates before sampling
            top_candidates = compute_logits_and_probs(
                next_token_logits,
                tokenizer,
                top_k=5,
                temperature=temperature,
                top_p=top_p
            )

            # Sample next token
            logits_f = next_token_logits.float()
            scaled_logits = logits_f / max(temperature, 0.01)

            if top_k > 0 and top_k < logits_f.size(-1):
                v, _ = torch.topk(scaled_logits, min(top_k, scaled_logits.size(-1)))
                scaled_logits[scaled_logits < v[-1]] = -float("Inf")

            probs = F.softmax(scaled_logits, dim=-1)

            if temperature < 0.01:
                next_token_id = torch.argmax(probs, dim=-1).unsqueeze(0)
            else:
                next_token_id = torch.multinomial(probs, num_samples=1)

            chosen_id = int(next_token_id.item())
            chosen_str = tokenizer.decode([chosen_id])

            generated_token_ids.append(chosen_id)
            accumulated_generated = tokenizer.decode(generated_token_ids, skip_special_tokens=True)

            step_traces.append({
                "step": step + 1,
                "chosen_token_id": chosen_id,
                "chosen_token_str": chosen_str,
                "chosen_display_str": "␣ (space)" if chosen_str == " " else ("↵ (newline)" if chosen_str == "\n" else chosen_str),
                "top_candidates": top_candidates,
                "accumulated_text": accumulated_generated,
                "full_context": formatted_prompt + tokenizer.decode(generated_token_ids)
            })

            if step_callback is not None:
                try:
                    step_callback(step + 1, max_new_tokens, chosen_str, accumulated_generated)
                except Exception:
                    pass

            # Stop if EOS token
            if chosen_id == tokenizer.eos_token_id:
                break

    full_generated_text = tokenizer.decode(generated_token_ids, skip_special_tokens=True)
    return full_generated_text, step_traces
