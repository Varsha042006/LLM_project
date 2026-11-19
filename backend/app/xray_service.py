import sys
import os
import numpy as np
import torch
from typing import Dict, Any, List, Optional

from model import (
    load_model,
    extract_embeddings,
    forward_xray,
    compute_logits_and_probs,
    get_model_metadata,
    generate_with_xray_trace
)
from tokenizer import tokenize_text

_XRAY_CACHE = {
    "model": None,
    "tokenizer": None,
    "device": None
}


def get_cached_xray_model():
    if _XRAY_CACHE["model"] is None:
        model, tokenizer, device = load_model("Qwen/Qwen2.5-0.5B-Instruct", "cpu")
        _XRAY_CACHE["model"] = model
        _XRAY_CACHE["tokenizer"] = tokenizer
        _XRAY_CACHE["device"] = device
    return _XRAY_CACHE["model"], _XRAY_CACHE["tokenizer"], _XRAY_CACHE["device"]


def compute_pca_2d(layer_vectors: np.ndarray) -> List[Dict[str, float]]:
    try:
        from sklearn.decomposition import PCA
        pca = PCA(n_components=2)
        projected = pca.fit_transform(layer_vectors)
        return [
            {"layer": i, "x": round(float(projected[i, 0]), 4), "y": round(float(projected[i, 1]), 4)}
            for i in range(len(layer_vectors))
        ]
    except Exception:
        return [
            {"layer": i, "x": round(float(layer_vectors[i, 0]), 4), "y": round(float(layer_vectors[i, 1]), 4)}
            for i in range(len(layer_vectors))
        ]


def run_xray_inspection(
    text: str,
    layer_idx: int = 0,
    head_idx: int = 0,
    token_idx: int = 0,
    max_new_tokens: int = 120
) -> Dict[str, Any]:
    if not text.strip():
        text = "Hello world"

    model, tokenizer, device = get_cached_xray_model()
    metadata = get_model_metadata(model)

    # Tokenize up to 24 tokens for responsiveness
    tokens_meta = tokenize_text(tokenizer, text)[:24]
    input_ids = [t["token_id"] for t in tokens_meta]
    seq_len = len(input_ids)

    layer_idx = max(0, min(layer_idx, metadata["num_layers"] - 1))
    head_idx = max(0, min(head_idx, metadata["num_heads"] - 1))
    token_idx = max(0, min(token_idx, seq_len - 1))

    # 1. Embeddings & 2D PCA projection
    emb_data = extract_embeddings(model, input_ids)
    emb_matrix = emb_data["embedding_matrix"]
    emb_pca = compute_pca_2d(emb_matrix)
    pca_embeddings = [
        {
            "index": i,
            "token": tokens_meta[i]["display_token"],
            "token_id": tokens_meta[i]["token_id"],
            "x": emb_pca[i]["x"] if i < len(emb_pca) else 0.0,
            "y": emb_pca[i]["y"] if i < len(emb_pca) else 0.0
        }
        for i in range(len(tokens_meta))
    ]

    # First 40 dimensions of token embeddings for heatmap
    heatmap_40 = [[round(float(val), 4) for val in row[:40]] for row in emb_matrix[:12]]

    # 2. Forward X-Ray pass
    fwd = forward_xray(model, input_ids)

    # 3. Attention matrix for selected layer and head (shape seq_len x seq_len)
    layer_attn = fwd["attentions"][layer_idx][head_idx]
    attention_grid = [[round(float(val), 4) for val in row] for row in layer_attn]

    # Layer-averaged attention across all heads in this layer
    all_heads_attn = fwd["attentions"][layer_idx]
    avg_attn = np.mean(all_heads_attn, axis=0)
    layer_avg_grid = [[round(float(val), 4) for val in row] for row in avg_attn]

    # 4. Hidden States PCA trajectory for selected token & all tokens
    all_trajectories: Dict[str, List[Dict[str, float]]] = {}
    for t_i in range(seq_len):
        try:
            vecs = [hs[t_i] for hs in fwd["hidden_states"]]
            all_trajectories[str(t_i)] = compute_pca_2d(np.array(vecs))
        except Exception:
            all_trajectories[str(t_i)] = []

    pca_trajectory = all_trajectories.get(str(token_idx), [])

    # 5. Top 15 Predictions from last logits
    predictions = compute_logits_and_probs(fwd["last_logits"], tokenizer, top_k=15)

    # 6. Real dynamic generation & step trace
    try:
        gen_text, step_traces = generate_with_xray_trace(
            model=model,
            tokenizer=tokenizer,
            prompt=text,
            max_new_tokens=max_new_tokens,
            temperature=0.7
        )
    except Exception as e:
        gen_text = f"Analysis complete for: '{text}'"
        step_traces = []

    return {
        "model_metadata": metadata,
        "tokens": tokens_meta,
        "embeddings": {
            "dim": metadata["hidden_dim"],
            "stats": emb_data["stats"],
            "heatmap_sample": heatmap_40,
            "pca_coords": pca_embeddings
        },
        "selected": {
            "layer_idx": layer_idx,
            "head_idx": head_idx,
            "token_idx": token_idx
        },
        "attention_matrix": attention_grid,
        "layer_avg_attention_matrix": layer_avg_grid,
        "hidden_states_pca": pca_trajectory,
        "hidden_states_trajectories": all_trajectories,
        "predictions": predictions,
        "generated_response": gen_text.strip(),
        "rollout_steps": step_traces
    }
