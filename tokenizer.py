"""
Tokenizer utility module for LLM X-Ray.
Handles text tokenization, token ID extraction, and formatting for visualization.
"""

import sys
import os
# Prevent slow TensorFlow detection during Transformers import
if "tensorflow" not in sys.modules:
    sys.modules["tensorflow"] = None

from typing import List, Dict, Any
from transformers import AutoTokenizer


def resolve_local_model_path(model_name: str) -> str:
    """Resolves local snapshot directory if cached to prevent huggingface.co network calls."""
    if os.path.isdir(model_name):
        return model_name
    cache_dir = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    hub_dir = os.path.join(cache_dir, "hub")
    folder_name = "models--" + model_name.replace("/", "--")
    snapshots_dir = os.path.join(hub_dir, folder_name, "snapshots")
    if os.path.isdir(snapshots_dir):
        snapshots = os.listdir(snapshots_dir)
        if snapshots:
            return os.path.join(snapshots_dir, snapshots[0])
    return model_name


def load_tokenizer(model_name: str = "Qwen/Qwen2.5-1.5B-Instruct") -> AutoTokenizer:
    """Load and return the tokenizer for the specified model."""
    target_path = resolve_local_model_path(model_name)
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
    return tokenizer


def tokenize_text(tokenizer: AutoTokenizer, text: str) -> List[Dict[str, Any]]:
    """
    Tokenizes the input text and returns detailed token information.
    
    Returns a list of dicts with:
    - index: 0-based token index
    - token_id: numerical ID
    - raw_token: raw token representation (e.g., Byte-BPE symbol)
    - decoded_token: clean human-readable decoded string
    - display_token: sanitized string suitable for web UI badges
    """
    if not text:
        return []

    input_ids = tokenizer.encode(text, add_special_tokens=False)
    raw_tokens = tokenizer.convert_ids_to_tokens(input_ids)
    
    token_details = []
    for idx, (token_id, raw_tok) in enumerate(zip(input_ids, raw_tokens)):
        decoded_tok = tokenizer.decode([token_id])
        
        # Clean up display tokens for UI (replace space symbols or newlines nicely)
        display_tok = decoded_tok
        if display_tok == " ":
            display_tok = "␣ (space)"
        elif display_tok == "\n":
            display_tok = "↵ (newline)"
        elif display_tok == "\t":
            display_tok = "⇥ (tab)"
            
        token_details.append({
            "index": idx,
            "token_id": int(token_id),
            "raw_token": str(raw_tok),
            "decoded_token": decoded_tok,
            "display_token": display_tok,
            "char_length": len(decoded_tok)
        })
        
    return token_details


def format_step4_flow(token_details: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Formats tokens and IDs for Step 4 visual pipeline display:
    Input: What is AI?
    Tokens: What | is | AI | ?
    Token IDs: 3838 | 374 | 15235 | 30
    """
    if not token_details:
        return {"tokens_str": "", "ids_str": ""}
        
    tokens_str = " | ".join([t["display_token"] for t in token_details])
    ids_str = " | ".join([str(t["token_id"]) for t in token_details])
    
    return {
        "tokens_str": tokens_str,
        "ids_str": ids_str
    }
