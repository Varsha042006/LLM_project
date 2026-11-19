"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Activity,
  Layers,
  Cpu,
  Eye,
  TrendingUp,
  BarChart3,
  Loader2,
  Sliders,
  Sparkles,
  ArrowRight,
  Hash
} from "lucide-react";
import { XRayData, inspectXRay } from "../lib/api";

interface XRayDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  initialText?: string;
}

export const XRayDrawer: React.FC<XRayDrawerProps> = ({
  isOpen,
  onClose,
  initialText = "What is AI?",
}) => {
  const [prompt, setPrompt] = useState(initialText);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<XRayData | null>(null);

  // Active Tab
  const [activeTab, setActiveTab] = useState<"tokens" | "embeddings" | "architecture" | "attention" | "hidden_states" | "logits">("tokens");

  // Inspection Controls
  const [selectedLayer, setSelectedLayer] = useState<number>(0);
  const [selectedHead, setSelectedHead] = useState<number>(0);
  const [selectedTokenIdx, setSelectedTokenIdx] = useState<number>(0);

  useEffect(() => {
    if (isOpen) {
      if (initialText && initialText !== prompt) {
        setPrompt(initialText);
      }
      runInspection(initialText || prompt, selectedLayer, selectedHead, selectedTokenIdx);
    }
  }, [isOpen, initialText]);

  const runInspection = async (
    textToInspect: string,
    layer: number = selectedLayer,
    head: number = selectedHead,
    token: number = selectedTokenIdx
  ) => {
    if (!textToInspect.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await inspectXRay({
        text: textToInspect,
        layer_idx: layer,
        head_idx: head,
        token_idx: token,
      });
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed to run X-Ray inspection.");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-[#141414] border-l border-[#262626] shadow-2xl flex flex-col animate-in slide-in-from-right duration-200 select-none">
      {/* Drawer Header */}
      <div className="px-5 py-4 border-b border-[#262626] bg-[#181818] flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#10a37f]/20 border border-[#10a37f]/50 flex items-center justify-center text-[#10a37f] shadow-sm">
            <Activity className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-gray-100 flex items-center space-x-2">
              <span>Neural LLM X-Ray</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#10a37f]/20 text-[#10a37f] font-mono font-normal">
                LIVE TENSORS
              </span>
            </h2>
            <p className="text-[11px] text-gray-400">
              Qwen 2.5 0.5B · 24 Layers · 14 Attention Heads · 896 Dim
            </p>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-[#252525] transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Input Prompt Box */}
      <div className="p-4 border-b border-[#262626] bg-[#161616]">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            runInspection(prompt);
          }}
          className="flex items-center space-x-2"
        >
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Enter prompt for neural inspection..."
            className="flex-1 bg-[#1e1e1e] border border-[#333] focus:border-[#10a37f] rounded-xl px-3 py-1.5 text-xs text-gray-100 focus:outline-none"
          />
          <button
            type="submit"
            disabled={loading}
            className="px-3 py-1.5 rounded-xl bg-[#10a37f] hover:bg-[#0e8c6d] text-white text-xs font-semibold shadow-sm transition-all flex items-center space-x-1.5 disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            <span>Inspect</span>
          </button>
        </form>
      </div>

      {/* 6 Tabs Navigation */}
      <div className="flex border-b border-[#262626] bg-[#121212] overflow-x-auto text-xs font-medium">
        {[
          { id: "tokens", label: "Tokens", icon: Hash },
          { id: "embeddings", label: "Embeddings", icon: Layers },
          { id: "architecture", label: "Layers", icon: Cpu },
          { id: "attention", label: "Attention Heatmap", icon: Eye },
          { id: "hidden_states", label: "Hidden States (PCA)", icon: TrendingUp },
          { id: "logits", label: "Next-Token Logits", icon: BarChart3 },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center space-x-1.5 px-3.5 py-2.5 border-b-2 whitespace-nowrap transition-colors ${
                isActive
                  ? "border-[#10a37f] text-[#10a37f] font-semibold bg-[#1a1a1a]"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5 text-gray-200 text-xs">
        {loading && (
          <div className="flex flex-col items-center justify-center py-16 space-y-3">
            <Loader2 className="w-7 h-7 animate-spin text-[#10a37f]" />
            <span className="text-gray-400 text-xs">Executing local neural forward pass...</span>
          </div>
        )}

        {error && (
          <div className="p-3 bg-red-950/40 border border-red-800/60 rounded-xl text-xs text-red-200">
            ⚠️ {error}
          </div>
        )}

        {data && !loading && (
          <>
            {/* TAB 1: TOKENS */}
            {activeTab === "tokens" && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">
                    Tokenization Sequence ({data.tokens.length} tokens)
                  </h3>
                  <div className="flex flex-wrap gap-2 p-3 bg-[#1a1a1a] rounded-xl border border-[#2c2c2c]">
                    {data.tokens.map((tok) => {
                      const isSelected = tok.index === selectedTokenIdx;
                      return (
                        <button
                          key={tok.index}
                          onClick={() => {
                            setSelectedTokenIdx(tok.index);
                            runInspection(prompt, selectedLayer, selectedHead, tok.index);
                          }}
                          className={`px-2.5 py-1.5 rounded-lg border text-xs font-mono transition-all ${
                            isSelected
                              ? "bg-[#10a37f] border-[#10a37f] text-white shadow-md shadow-[#10a37f]/20 font-bold"
                              : "bg-[#252525] border-[#383838] text-gray-300 hover:border-[#10a37f]"
                          }`}
                        >
                          <span className="opacity-60 text-[10px] mr-1">#{tok.index}</span>
                          <span>{tok.display_token}</span>
                          <span className="opacity-50 text-[9px] ml-1.5">({tok.token_id})</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">
                    Token Details Table
                  </h3>
                  <div className="overflow-x-auto rounded-xl border border-[#2c2c2c]">
                    <table className="w-full text-left border-collapse text-[11px]">
                      <thead>
                        <tr className="bg-[#1f1f1f] text-gray-400 border-b border-[#2e2e2e]">
                          <th className="p-2">Pos</th>
                          <th className="p-2">Token ID</th>
                          <th className="p-2">Token Text</th>
                          <th className="p-2">Length</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.tokens.map((t) => (
                          <tr
                            key={t.index}
                            className={`border-b border-[#262626] hover:bg-[#222] ${
                              t.index === selectedTokenIdx ? "bg-[#10a37f]/10 text-white font-medium" : ""
                            }`}
                          >
                            <td className="p-2 font-mono text-gray-400">{t.index}</td>
                            <td className="p-2 font-mono text-[#10a37f]">{t.token_id}</td>
                            <td className="p-2 font-mono">{t.display_token}</td>
                            <td className="p-2 text-gray-400">{t.char_length} chars</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: EMBEDDINGS */}
            {activeTab === "embeddings" && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-[#1c1c1c] rounded-xl border border-[#2e2e2e]">
                    <span className="text-[11px] text-gray-400">Embedding Dimension</span>
                    <div className="text-base font-bold text-gray-100 mt-0.5">{data.embeddings.dim} float16</div>
                  </div>
                  <div className="p-3 bg-[#1c1c1c] rounded-xl border border-[#2e2e2e]">
                    <span className="text-[11px] text-gray-400">Total Tokens</span>
                    <div className="text-base font-bold text-gray-100 mt-0.5">{data.tokens.length} vectors</div>
                  </div>
                </div>

                <div>
                  <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">
                    L2 Vector Norms per Token
                  </h3>
                  <div className="space-y-2">
                    {data.embeddings.stats.map((s, idx) => {
                      const maxNorm = Math.max(...data.embeddings.stats.map((x) => x.norm), 1);
                      const pct = Math.min(100, Math.round((s.norm / maxNorm) * 100));
                      const tok = data.tokens[idx];
                      return (
                        <div key={idx} className="p-2.5 bg-[#1b1b1b] rounded-xl border border-[#2a2a2a] space-y-1">
                          <div className="flex justify-between items-center text-[11px]">
                            <span className="font-mono text-gray-300">
                              #{idx} "{tok?.display_token || ''}"
                            </span>
                            <span className="text-[#10a37f] font-mono">Norm: {s.norm}</span>
                          </div>
                          <div className="w-full bg-[#121212] h-2 rounded-full overflow-hidden">
                            <div className="bg-[#10a37f] h-full rounded-full transition-all" style={{ width: `${pct}%` }} />
                          </div>
                          <div className="flex justify-between text-[10px] text-gray-500 pt-0.5 font-mono">
                            <span>Mean: {s.mean}</span>
                            <span>Std: {s.std}</span>
                            <span>Slice[0..4]: [{s.slice.slice(0, 4).join(", ")}]</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: ARCHITECTURE & LAYER SELECTOR */}
            {activeTab === "architecture" && (
              <div className="space-y-5">
                <div className="grid grid-cols-3 gap-2.5">
                  <div className="p-2.5 bg-[#1c1c1c] rounded-xl border border-[#2e2e2e]">
                    <span className="text-[10px] text-gray-400 uppercase">Hidden Dim</span>
                    <div className="text-sm font-bold text-gray-100 mt-0.5">{data.model_metadata.hidden_dim}</div>
                  </div>
                  <div className="p-2.5 bg-[#1c1c1c] rounded-xl border border-[#2e2e2e]">
                    <span className="text-[10px] text-gray-400 uppercase">Attention Heads</span>
                    <div className="text-sm font-bold text-gray-100 mt-0.5">{data.model_metadata.num_heads}</div>
                  </div>
                  <div className="p-2.5 bg-[#1c1c1c] rounded-xl border border-[#2e2e2e]">
                    <span className="text-[10px] text-gray-400 uppercase">Parameters</span>
                    <div className="text-sm font-bold text-[#10a37f] mt-0.5">{data.model_metadata.num_parameters_formatted || '0.49B'}</div>
                  </div>
                </div>

                {/* Layer Slider */}
                <div className="p-4 bg-[#1a1a1a] rounded-xl border border-[#2c2c2c] space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-semibold text-gray-200">
                      Active Transformer Layer: <span className="text-[#10a37f]">Layer {selectedLayer + 1}</span> of {data.model_metadata.num_layers}
                    </span>
                    <span className="text-[10px] text-gray-400 font-mono">Index: {selectedLayer}</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={data.model_metadata.num_layers - 1}
                    value={selectedLayer}
                    onChange={(e) => {
                      const newL = parseInt(e.target.value);
                      setSelectedLayer(newL);
                      runInspection(prompt, newL, selectedHead, selectedTokenIdx);
                    }}
                    className="w-full accent-[#10a37f] cursor-pointer"
                  />
                </div>

                {/* Attention Head Grid */}
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-gray-300">
                    Attention Head (Head {selectedHead + 1} of {data.model_metadata.num_heads})
                  </span>
                  <div className="grid grid-cols-7 gap-1.5">
                    {Array.from({ length: data.model_metadata.num_heads }).map((_, hIdx) => (
                      <button
                        key={hIdx}
                        onClick={() => {
                          setSelectedHead(hIdx);
                          runInspection(prompt, selectedLayer, hIdx, selectedTokenIdx);
                        }}
                        className={`py-1.5 rounded-lg text-xs font-mono transition-all ${
                          selectedHead === hIdx
                            ? "bg-[#10a37f] text-white font-bold shadow-md shadow-[#10a37f]/20"
                            : "bg-[#222] text-gray-400 hover:text-white hover:bg-[#2a2a2a]"
                        }`}
                      >
                        H{hIdx + 1}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* TAB 4: ATTENTION HEATMAP */}
            {activeTab === "attention" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-300">
                    Attention Matrix: <span className="text-[#10a37f]">Layer {selectedLayer + 1}, Head {selectedHead + 1}</span>
                  </span>
                  <span className="text-[10px] text-gray-400 font-mono">
                    {data.tokens.length} × {data.tokens.length} Matrix
                  </span>
                </div>

                {/* Heatmap Grid */}
                <div className="overflow-x-auto p-3 bg-[#1a1a1a] rounded-xl border border-[#2c2c2c]">
                  <table className="border-collapse text-[10px]">
                    <thead>
                      <tr>
                        <th className="p-1"></th>
                        {data.tokens.map((t, cIdx) => (
                          <th key={cIdx} className="p-1 text-center font-mono text-gray-400 max-w-[50px] truncate" title={t.display_token}>
                            {t.display_token.slice(0, 4)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.attention_matrix.map((row, rIdx) => (
                        <tr key={rIdx}>
                          <td className="p-1 font-mono text-gray-400 text-right pr-2 max-w-[50px] truncate">
                            {data.tokens[rIdx]?.display_token.slice(0, 4)}
                          </td>
                          {row.map((val, cIdx) => {
                            const intensity = Math.min(1, Math.max(0, val));
                            return (
                              <td
                                key={cIdx}
                                className="p-1 text-center font-mono text-[9px] border border-[#262626] transition-colors"
                                style={{
                                  backgroundColor: `rgba(16, 163, 127, ${intensity})`,
                                  color: intensity > 0.4 ? "#fff" : "#888",
                                }}
                                title={`Attn(${data.tokens[rIdx]?.display_token} -> ${data.tokens[cIdx]?.display_token}): ${(val * 100).toFixed(1)}%`}
                              >
                                {(val * 100).toFixed(0)}%
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* TAB 5: HIDDEN STATES PCA TRAJECTORY */}
            {activeTab === "hidden_states" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-300">
                    2D PCA Trajectory for Token: <span className="text-[#10a37f]">"{data.tokens[selectedTokenIdx]?.display_token}"</span>
                  </span>
                  <span className="text-[10px] text-gray-400 font-mono">25 Layer Coordinates</span>
                </div>

                {/* SVG 2D Scatter / Path Visualizer */}
                <div className="relative w-full h-64 bg-[#181818] rounded-xl border border-[#2c2c2c] p-4 flex items-center justify-center overflow-hidden">
                  <svg className="w-full h-full" viewBox="-20 -20 240 240">
                    {/* Grid lines */}
                    <line x1="0" y1="100" x2="200" y2="100" stroke="#2a2a2a" strokeDasharray="2,2" />
                    <line x1="100" y1="0" x2="100" y2="200" stroke="#2a2a2a" strokeDasharray="2,2" />

                    {/* Path connecting layers */}
                    {data.hidden_states_pca.length > 1 && (
                      <polyline
                        fill="none"
                        stroke="#10a37f"
                        strokeWidth="1.5"
                        strokeOpacity="0.7"
                        points={data.hidden_states_pca
                          .map((pt) => {
                            const px = 100 + pt.x * 6;
                            const py = 100 - pt.y * 6;
                            return `${px},${py}`;
                          })
                          .join(" ")}
                      />
                    )}

                    {/* Points per layer */}
                    {data.hidden_states_pca.map((pt, pIdx) => {
                      const px = 100 + pt.x * 6;
                      const py = 100 - pt.y * 6;
                      const isFirst = pIdx === 0;
                      const isLast = pIdx === data.hidden_states_pca.length - 1;
                      return (
                        <circle
                          key={pIdx}
                          cx={px}
                          cy={py}
                          r={isFirst || isLast ? 3.5 : 2}
                          fill={isFirst ? "#3b82f6" : isLast ? "#ef4444" : "#10a37f"}
                        >
                          <title>Layer {pt.layer}: ({pt.x}, {pt.y})</title>
                        </circle>
                      );
                    })}
                  </svg>
                  <div className="absolute bottom-2 right-3 text-[10px] text-gray-500 font-mono space-x-2">
                    <span className="text-blue-400">● Layer 0 (Embedding)</span>
                    <span className="text-red-400">● Layer 24 (Final)</span>
                  </div>
                </div>

                <div className="text-[11px] text-gray-400 italic">
                  💡 The trajectory illustrates how the token vector transitions from raw morphological embeddings into deep semantic hidden states through 24 self-attention layers.
                </div>
              </div>
            )}

            {/* TAB 6: LOGITS & NEXT-TOKEN PREDICTIONS */}
            {activeTab === "logits" && (
              <div className="space-y-4">
                <span className="text-xs font-semibold text-gray-300">
                  Top 10 Candidate Next Tokens (Softmax Probabilities)
                </span>
                <div className="space-y-2">
                  {data.predictions.map((pred) => (
                    <div
                      key={pred.rank}
                      className="p-2.5 bg-[#1b1b1b] rounded-xl border border-[#2a2a2a] space-y-1"
                    >
                      <div className="flex justify-between items-center text-[11px]">
                        <div className="flex items-center space-x-2 font-mono">
                          <span className="text-gray-500">#{pred.rank}</span>
                          <span className="font-bold text-gray-100">"{pred.display_str}"</span>
                          <span className="text-gray-500 text-[10px]">(ID: {pred.token_id})</span>
                        </div>
                        <div className="flex items-center space-x-2 font-mono">
                          <span className="text-gray-400 text-[10px]">Logit: {pred.logit}</span>
                          <span className="text-[#10a37f] font-bold">{pred.percentage}%</span>
                        </div>
                      </div>
                      <div className="w-full bg-[#121212] h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-[#10a37f] h-full rounded-full transition-all"
                          style={{ width: `${Math.max(pred.percentage, 2)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

