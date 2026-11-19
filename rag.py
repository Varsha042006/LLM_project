"""
RAG (Retrieval-Augmented Generation) module for LocalGPT Pro.
Features per-user FAISS vector indexing, dense semantic embeddings,
similarity search, and grounded source citation synthesis.
"""

import os
import json
import numpy as np
import faiss
import torch
from typing import List, Dict, Any, Tuple, Optional

INDEX_BASE_DIR = "indexes"


def get_user_index_dir(user_id: str) -> str:
    """Returns the per-user index directory path."""
    path = os.path.join(INDEX_BASE_DIR, user_id)
    os.makedirs(path, exist_ok=True)
    return path


def compute_dense_embedding(
    text: str,
    model: Any,
    tokenizer: Any,
    max_length: int = 256
) -> np.ndarray:
    """
    Computes a normalized dense vector embedding using the local Qwen model's embedding layer.
    Uses mean-pooling across token embeddings and L2 normalization for cosine similarity.
    """
    if not text.strip():
        # Return zero vector of appropriate dimension
        dim = model.config.hidden_size
        return np.zeros((dim,), dtype=np.float32)

    tokens = tokenizer.encode(text, truncation=True, max_length=max_length)
    if not tokens:
        tokens = [tokenizer.eos_token_id or 0]

    device = next(model.parameters()).device
    tensor_ids = torch.tensor([tokens], device=device, dtype=torch.long)
    embed_layer = model.get_input_embeddings()

    with torch.inference_mode():
        token_embeds = embed_layer(tensor_ids)[0] # (seq_len, hidden_dim)
        mean_embed = token_embeds.mean(dim=0).cpu().float().numpy()

    # L2 normalize for cosine similarity
    norm = np.linalg.norm(mean_embed)
    if norm > 1e-6:
        mean_embed = mean_embed / norm
    return mean_embed.astype(np.float32)


def get_user_faiss_index(user_id: str, embed_dim: int) -> Tuple[faiss.Index, List[Dict[str, Any]]]:
    """Loads or creates a per-user FAISS IndexFlatIP (cosine similarity)."""
    user_dir = get_user_index_dir(user_id)
    index_path = os.path.join(user_dir, "faiss.index")
    meta_path = os.path.join(user_dir, "chunks.json")

    if os.path.exists(index_path) and os.path.exists(meta_path):
        try:
            index = faiss.read_index(index_path)
            with open(meta_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            # Verify dimension match
            if index.d == embed_dim:
                return index, chunks
        except Exception:
            pass

    # Create new IndexFlatIP (Inner Product = Cosine Similarity with normalized vectors)
    index = faiss.IndexFlatIP(embed_dim)
    return index, []


def save_user_faiss_index(user_id: str, index: faiss.Index, chunks: List[Dict[str, Any]]):
    """Persists the user's FAISS index and chunk metadata."""
    user_dir = get_user_index_dir(user_id)
    index_path = os.path.join(user_dir, "faiss.index")
    meta_path = os.path.join(user_dir, "chunks.json")

    faiss.write_index(index, index_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)


def index_user_document_chunks(
    user_id: str,
    new_chunks: List[Dict[str, Any]],
    model: Any,
    tokenizer: Any
) -> int:
    """
    Computes embeddings for new document chunks and adds them to the user's isolated FAISS index.
    """
    if not new_chunks:
        return 0

    embed_dim = model.config.hidden_size
    index, existing_chunks = get_user_faiss_index(user_id, embed_dim)

    # Compute embeddings
    embeddings = []
    for c in new_chunks:
        vec = compute_dense_embedding(c["content"], model, tokenizer)
        embeddings.append(vec)

    emb_matrix = np.vstack(embeddings).astype(np.float32)
    index.add(emb_matrix)

    all_chunks = existing_chunks + new_chunks
    save_user_faiss_index(user_id, index, all_chunks)
    return len(new_chunks)


def remove_document_from_user_faiss_index(
    user_id: str,
    filename: str,
    model: Any,
    tokenizer: Any
) -> int:
    """
    Removes all chunks associated with a specific filename from the user's FAISS index
    and rebuilds the index with the remaining chunks.
    """
    embed_dim = model.config.hidden_size
    _, chunks = get_user_faiss_index(user_id, embed_dim)
    remaining_chunks = [c for c in chunks if c.get("filename") != filename]

    new_index = faiss.IndexFlatIP(embed_dim)
    if remaining_chunks:
        embeddings = [compute_dense_embedding(c["content"], model, tokenizer) for c in remaining_chunks]
        emb_matrix = np.vstack(embeddings).astype(np.float32)
        new_index.add(emb_matrix)

    save_user_faiss_index(user_id, new_index, remaining_chunks)
    return len(remaining_chunks)


def clear_user_faiss_index(user_id: str, embed_dim: int):
    """Completely resets the user's FAISS index and chunk metadata."""
    new_index = faiss.IndexFlatIP(embed_dim)
    save_user_faiss_index(user_id, new_index, [])


def retrieve_relevant_chunks(
    user_id: str,
    query: str,
    model: Any,
    tokenizer: Any,
    top_k: int = 3,
    min_score: float = 0.15
) -> List[Dict[str, Any]]:
    """
    Searches the user's isolated FAISS index for relevant document passages.
    Returns matched chunks with source metadata and similarity scores.
    """
    embed_dim = model.config.hidden_size
    index, chunks = get_user_faiss_index(user_id, embed_dim)

    if index.ntotal == 0 or not chunks:
        return []

    query_vec = compute_dense_embedding(query, model, tokenizer)
    query_matrix = np.array([query_vec], dtype=np.float32)

    actual_k = min(top_k, index.ntotal)
    scores, indices = index.search(query_matrix, actual_k)

    results = []
    for rank in range(actual_k):
        idx = int(indices[0][rank])
        score = float(scores[0][rank])
        if idx >= 0 and idx < len(chunks) and score >= min_score:
            chunk_data = dict(chunks[idx])
            chunk_data["score"] = round(score, 4)
            chunk_data["rank"] = rank + 1
            results.append(chunk_data)

    return results


def build_rag_prompt(query: str, retrieved_chunks: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Formats the RAG prompt with numbered source contexts and instructions for citations.
    """
    if not retrieved_chunks:
        return query, []

    context_blocks = []
    sources_summary = []

    for idx, c in enumerate(retrieved_chunks):
        ref_num = idx + 1
        src_label = f"Source {ref_num}: {c['filename']} (Page {c.get('page', 1)})"
        context_blocks.append(f"[{src_label}]\n{c['content']}")
        sources_summary.append({
            "ref": ref_num,
            "filename": c["filename"],
            "page": c.get("page", 1),
            "score": c.get("score", 0.0),
            "snippet": c["content"][:160] + "..." if len(c["content"]) > 160 else c["content"]
        })

    full_context = "\n\n".join(context_blocks)
    
    rag_prompt = f"""You are LocalGPT Pro, an intelligent private local AI assistant.
Answer the user's question accurately using ONLY the verified context below.
Always cite your sources using [Source X] references where appropriate. If the context does not contain the answer, state that clearly.

--- CONTEXT DOCUMENTS ---
{full_context}
-------------------------

User Question: {query}

Answer:"""
    return rag_prompt, sources_summary
