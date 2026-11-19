"""
Visualization utilities for LLM X-Ray.
Generates interactive Plotly figures for Embeddings PCA, Attention Heatmaps,
Hidden State trajectories, Logits/Probabilities, and Token Generation flows.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.decomposition import PCA
from typing import List, Dict, Any, Optional, Tuple


# Dark Cyberpunk / Neural Matrix Color Palette for X-Ray UI
BG_COLOR = "#0e1117"
CARD_BG = "#161b22"
PRIMARY_CYAN = "#00f0ff"
SECONDARY_MAGENTA = "#ff007f"
ACCENT_PURPLE = "#8a2be2"
TEXT_COLOR = "#f0f6fc"
GRID_COLOR = "#30363d"


def create_pca_embedding_plot(
    embedding_matrix: np.ndarray,
    tokens: List[Dict[str, Any]]
) -> go.Figure:
    """
    Step 5: Visualizes high-dimensional token embeddings projected to 2D using PCA.
    """
    seq_len, embed_dim = embedding_matrix.shape
    
    # Perform PCA reduction to 2D
    if seq_len == 0:
        coords = np.zeros((0, 2))
    elif seq_len == 1:
        coords = np.zeros((1, 2))
    else:
        n_components = min(2, seq_len, embed_dim)
        pca = PCA(n_components=n_components)
        coords = pca.fit_transform(embedding_matrix)
        if coords.shape[1] == 1:
            coords = np.hstack([coords, np.zeros((seq_len, 1))])

    df = pd.DataFrame({
        "x": coords[:, 0] if coords.shape[0] > 0 else [],
        "y": coords[:, 1] if coords.shape[0] > 0 else [],
        "Token": [t["display_token"] for t in tokens],
        "Token ID": [t["token_id"] for t in tokens],
        "Index": [t["index"] for t in tokens],
        "Raw": [t["raw_token"] for t in tokens]
    })

    fig = px.scatter(
        df,
        x="x",
        y="y",
        text="Token",
        hover_data=["Index", "Token ID", "Raw"],
        title=f"🧬 2D PCA Projection of Token Embeddings (Dimension: {embed_dim})",
        labels={"x": "PCA Component 1", "y": "PCA Component 2"}
    )

    fig.update_traces(
        marker=dict(
            size=16,
            color=df["Index"],
            colorscale="Viridis",
            showscale=True,
            line=dict(width=2, color=PRIMARY_CYAN)
        ),
        textposition="top center",
        textfont=dict(size=13, color=TEXT_COLOR)
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=CARD_BG,
        font=dict(color=TEXT_COLOR),
        xaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
        yaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
        height=480
    )

    return fig


def create_embedding_heatmap_matrix(
    embedding_matrix: np.ndarray,
    tokens: List[Dict[str, Any]],
    max_dims: int = 40
) -> go.Figure:
    """
    Step 5: Heatmap showing first 40 vector values of input token embeddings.
    """
    seq_len, embed_dim = embedding_matrix.shape
    if seq_len == 0:
        fig = go.Figure()
        fig.update_layout(
            title="📐 Embedding Vector Snapshot (Empty)",
            template="plotly_dark",
            paper_bgcolor=BG_COLOR,
            plot_bgcolor=CARD_BG,
            font=dict(color=TEXT_COLOR)
        )
        return fig

    preview_dim = min(embed_dim, max_dims)
    sub_matrix = embedding_matrix[:, :preview_dim]

    token_labels = [f"[{t['index']}] {t['display_token']}" for t in tokens]

    fig = go.Figure(
        data=go.Heatmap(
            z=sub_matrix,
            x=[f"D{i}" for i in range(preview_dim)],
            y=token_labels,
            colorscale="Electric",
            colorbar=dict(title="Value")
        )
    )

    fig.update_layout(
        title=f"📐 Embedding Vector Snapshot (First {preview_dim} of {embed_dim} dimensions)",
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=CARD_BG,
        font=dict(color=TEXT_COLOR),
        xaxis=dict(title="Embedding Dimension"),
        yaxis=dict(title="Token"),
        height=380
    )

    return fig


def create_attention_heatmap(
    attention_matrix: np.ndarray,
    tokens: List[Dict[str, Any]],
    layer_idx: int,
    head_idx: int
) -> go.Figure:
    """
    Step 7: Displays Attention Heatmap for specified Layer and Attention Head.
    attention_matrix shape: (seq_len, seq_len)
    """
    if len(tokens) == 0 or attention_matrix.size == 0:
        fig = go.Figure()
        fig.update_layout(
            title=f"👁️ Self-Attention Heatmap — Layer {layer_idx + 1}, Head {head_idx + 1} (Empty)",
            template="plotly_dark",
            paper_bgcolor=BG_COLOR,
            plot_bgcolor=CARD_BG,
            font=dict(color=TEXT_COLOR)
        )
        return fig

    token_labels = [t["display_token"] for t in tokens]

    fig = go.Figure(
        data=go.Heatmap(
            z=attention_matrix,
            x=token_labels,
            y=token_labels,
            colorscale="Plasma",
            zmin=0.0,
            zmax=1.0,
            colorbar=dict(title="Attention Weight"),
            hovertemplate="Query (Row): %{y}<br>Key (Col): %{x}<br>Weight: %{z:.4f}<extra></extra>"
        )
    )

    # Annotate values if sequence is short
    if len(tokens) <= 12:
        annotations = []
        for r in range(len(tokens)):
            for c in range(len(tokens)):
                val = attention_matrix[r, c]
                color = "white" if val < 0.6 else "black"
                annotations.append(
                    dict(
                        x=token_labels[c],
                        y=token_labels[r],
                        text=f"{val:.2f}",
                        showarrow=False,
                        font=dict(color=color, size=11)
                    )
                )
        fig.update_layout(annotations=annotations)

    fig.update_layout(
        title=f"👁️ Self-Attention Heatmap — Layer {layer_idx + 1}, Head {head_idx + 1}",
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=CARD_BG,
        font=dict(color=TEXT_COLOR),
        xaxis=dict(title="Keys (Attended To) →", gridcolor=GRID_COLOR),
        yaxis=dict(title="Queries (Attending From) ↑", gridcolor=GRID_COLOR, autorange="reversed"),
        height=500
    )

    return fig


def create_hidden_states_pca_trajectory(
    hidden_states_list: List[np.ndarray],
    tokens: List[Dict[str, Any]],
    selected_token_idx: int = -1
) -> go.Figure:
    """
    Step 8: PCA trajectory showing how a selected token's representation evolves across layers (Layer 0..N).
    hidden_states_list: list of length num_layers + 1, each shape (seq_len, hidden_dim)
    """
    if not hidden_states_list or not tokens:
        fig = go.Figure()
        fig.update_layout(
            title="🌌 Hidden State Evolution Trajectory (Empty)",
            template="plotly_dark",
            paper_bgcolor=BG_COLOR,
            plot_bgcolor=CARD_BG,
            font=dict(color=TEXT_COLOR)
        )
        return fig

    # Safely clamp token index for label lookup
    safe_token_lookup_idx = min(max(0, selected_token_idx), len(tokens) - 1)
    target_token = tokens[safe_token_lookup_idx].get("display_token", f"Token {safe_token_lookup_idx}")

    # Safely collect layer vectors across all layers
    layer_vectors = []
    layer_names = []

    for l in range(len(hidden_states_list)):
        hs_layer = hidden_states_list[l]
        if hs_layer is None or hs_layer.size == 0:
            continue

        if hs_layer.ndim == 1:
            vec = hs_layer
        elif hs_layer.ndim >= 2:
            if hs_layer.ndim == 3:
                hs_layer = hs_layer[0]
            max_idx = hs_layer.shape[0] - 1
            if max_idx < 0:
                continue
            safe_idx = min(max(0, selected_token_idx), max_idx)
            vec = hs_layer[safe_idx]
        else:
            continue

        layer_vectors.append(vec)
        layer_name = "Layer 0 (Embed)" if l == 0 else f"Layer {l}"
        layer_names.append(layer_name)

    if len(layer_vectors) < 2:
        fig = go.Figure()
        fig.update_layout(
            title=f"🌌 Hidden State Trajectory for '{target_token}' (Insufficient Layers)",
            template="plotly_dark",
            paper_bgcolor=BG_COLOR,
            plot_bgcolor=CARD_BG,
            font=dict(color=TEXT_COLOR)
        )
        return fig

    layer_vectors = np.array(layer_vectors) # (num_valid_layers, hidden_dim)

    # Perform PCA reduction
    n_comp = min(2, layer_vectors.shape[0], layer_vectors.shape[1])
    if n_comp < 2:
        coords = np.zeros((layer_vectors.shape[0], 2))
    else:
        pca = PCA(n_components=2)
        coords = pca.fit_transform(layer_vectors)

    num_layers = max(0, len(layer_vectors) - 1)
    df = pd.DataFrame({
        "x": coords[:, 0],
        "y": coords[:, 1],
        "Layer": layer_names,
        "Layer Index": list(range(len(layer_vectors)))
    })

    fig = go.Figure()

    # Line trajectory trace
    fig.add_trace(
        go.Scatter(
            x=df["x"],
            y=df["y"],
            mode="lines+markers+text",
            text=[f"L{i}" if i % 5 == 0 or i == num_layers else "" for i in range(len(layer_vectors))],
            textposition="top center",
            line=dict(color=PRIMARY_CYAN, width=3, dash="solid"),
            marker=dict(
                size=12,
                color=df["Layer Index"],
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="Layer Depth")
            ),
            hovertext=df["Layer"],
            name="Representation Flow"
        )
    )

    fig.update_layout(
        title=f"🌌 Hidden State Evolution Trajectory for Token: '{target_token}' (Layer 0 → {num_layers})",
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=CARD_BG,
        font=dict(color=TEXT_COLOR),
        xaxis=dict(title="PCA Component 1", gridcolor=GRID_COLOR),
        yaxis=dict(title="PCA Component 2", gridcolor=GRID_COLOR),
        height=500
    )

    return fig


def create_logits_bar_chart(
    predictions: List[Dict[str, Any]],
    top_k: int = 10
) -> go.Figure:
    """
    Step 9: Horizontal Bar Chart showing Top-K predicted next tokens and Softmax Probabilities.
    """
    df = pd.DataFrame(predictions[:top_k])
    # Reverse so top probability is at the top of horizontal bar chart
    df = df.iloc[::-1]

    fig = go.Figure(
        data=go.Bar(
            x=df["percentage"],
            y=[f"'{t}' (ID: {id_})" for t, id_ in zip(df["display_str"], df["token_id"])],
            orientation="h",
            text=[f"{p:.2f}% (Logit: {l:.2f})" for p, l in zip(df["percentage"], df["logit"])],
            textposition="inside",
            insidetextanchor="end",
            marker=dict(
                color=df["percentage"],
                colorscale="Tealgrn",
                line=dict(color=PRIMARY_CYAN, width=1)
            )
        )
    )

    fig.update_layout(
        title=f"📊 Next-Token Softmax Probability Distribution (Top {len(df)} Candidates)",
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=CARD_BG,
        font=dict(color=TEXT_COLOR),
        xaxis=dict(title="Probability (%)", range=[0, 105], gridcolor=GRID_COLOR),
        yaxis=dict(title="Candidate Token", gridcolor=GRID_COLOR),
        height=420
    )

    return fig


def create_step_generation_flow(
    step_traces: List[Dict[str, Any]],
    current_step_idx: int = 0
) -> Tuple[go.Figure, Dict[str, Any]]:
    """
    Step 10: Visualizes the step-by-step token generation rollout.
    """
    if not step_traces:
        empty_fig = go.Figure()
        return empty_fig, {}

    current_step_idx = max(0, min(current_step_idx, len(step_traces) - 1))
    step_data = step_traces[current_step_idx]

    candidates = step_data["top_candidates"]
    df = pd.DataFrame(candidates)
    df = df.iloc[::-1] # Reverse for horizontal bar plot

    # Mark chosen token with distinct color
    colors = [
        SECONDARY_MAGENTA if c["token_id"] == step_data["chosen_token_id"] else "#1f6feb"
        for c in df.to_dict("records")
    ]

    fig = go.Figure(
        data=go.Bar(
            x=df["percentage"],
            y=[f"'{c['display_str']}'" for c in candidates[::-1]],
            orientation="h",
            text=[f"{p:.1f}% {'★ (Selected)' if c['token_id'] == step_data['chosen_token_id'] else ''}" for p, c in zip(df["percentage"], candidates[::-1])],
            textposition="auto",
            marker=dict(color=colors)
        )
    )

    fig.update_layout(
        title=f"🎬 Generation Step {step_data['step']} — Chosen Token: '{step_data['chosen_display_str']}'",
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=CARD_BG,
        font=dict(color=TEXT_COLOR),
        xaxis=dict(title="Probability (%)", range=[0, 105], gridcolor=GRID_COLOR),
        yaxis=dict(title="Candidate Pool"),
        height=360
    )

    return fig, step_data
