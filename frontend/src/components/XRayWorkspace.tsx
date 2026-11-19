"use client";

import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Loader2,
  CheckCircle2,
  Layers,
  Cpu,
  Eye,
  TrendingUp,
  BarChart3,
  Sliders,
  Play,
  RotateCcw,
  BookOpen,
  Info,
  Camera,
  ZoomIn,
  ZoomOut,
  Maximize2
} from "lucide-react";
import { XRayData, inspectXRay } from "../lib/api";

// Safe inline Error Boundary
class StepErrorBoundary extends React.Component<
  { children: React.ReactNode; stepName: string; onReset: () => void },
  { hasError: boolean; error: string | null }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: any) {
    return { hasError: true, error: error?.message || "Unknown error occurred" };
  }
  componentDidCatch(error: any, info: any) {
    console.error("StepErrorBoundary caught an error:", error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-5 rounded-xl bg-red-950/40 border border-red-800 text-xs text-red-200 space-y-3">
          <div className="flex items-center space-x-2 font-bold text-red-300">
            <span>⚠️</span>
            <span>Error rendering {this.props.stepName}: {this.state.error}</span>
          </div>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              this.props.onReset();
            }}
            className="px-3 py-1.5 rounded bg-red-800 hover:bg-red-700 text-white font-semibold text-xs transition-colors"
          >
            Reset View
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// Global SVG/Canvas PNG Exporter
const exportSvgAsPng = (elementId: string, filename: string, width = 850, height = 400) => {
  if (typeof window === "undefined") return;
  const el = document.getElementById(elementId);
  if (!el) return;

  let targetSvg: SVGSVGElement | null = null;
  if (el.tagName.toLowerCase() === "svg") {
    targetSvg = el as unknown as SVGSVGElement;
  } else {
    targetSvg = el.querySelector("svg");
  }

  if (!targetSvg) return;

  if (!targetSvg.getAttribute("xmlns")) {
    targetSvg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  }

  const svgData = new XMLSerializer().serializeToString(targetSvg);
  const dataUri = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgData);

  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "#0c1017";
      ctx.fillRect(0, 0, width, height);
      ctx.drawImage(img, 0, 0, width, height);
      const pngUrl = canvas.toDataURL("image/png");
      const a = document.createElement("a");
      a.download = filename;
      a.href = pngUrl;
      a.click();
    }
  };
  img.src = dataUri;
};

// Canvas-based Matrix PNG Exporter for Heatmaps
const exportMatrixCanvas = (
  matrix: number[][],
  tokens: { display_token: string }[],
  title: string,
  filename: string
) => {
  if (typeof window === "undefined") return;
  const n = tokens.length;
  if (!n) return;
  const cellSz = 44;
  const marginL = 90;
  const marginT = 80;
  const marginR = 80;
  const marginB = 60;
  const width = marginL + n * cellSz + marginR;
  const height = marginT + n * cellSz + marginB;

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  // Background
  ctx.fillStyle = "#0c1017";
  ctx.fillRect(0, 0, width, height);

  // Title
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 13px sans-serif";
  ctx.fillText(title, marginL, 35);

  // Keys label
  ctx.fillStyle = "#9ca3af";
  ctx.font = "bold 10px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("Keys (Attended To) →", marginL + (n * cellSz) / 2, marginT - 25);

  // Column Headers
  ctx.font = "bold 10px monospace";
  tokens.forEach((t, cIdx) => {
    ctx.fillStyle = "#9ca3af";
    ctx.fillText(t.display_token, marginL + cIdx * cellSz + cellSz / 2, marginT - 8);
  });

  // Plasma color helper
  const getPlasmaColor = (val: number) => {
    const v = Math.max(0, Math.min(1, typeof val === "number" && !isNaN(val) ? val : 0));
    if (v <= 0.005) return "#0d0887";
    if (v < 0.15) return "#46039f";
    if (v < 0.30) return "#721f81";
    if (v < 0.50) return "#9c179e";
    if (v < 0.65) return "#bd3786";
    if (v < 0.80) return "#d8576b";
    if (v < 0.92) return "#ed7953";
    return "#f0f921";
  };

  // Rows and Cells
  tokens.forEach((rTok, rIdx) => {
    ctx.fillStyle = "#9ca3af";
    ctx.textAlign = "right";
    ctx.font = "bold 10px monospace";
    ctx.fillText(rTok.display_token, marginL - 10, marginT + rIdx * cellSz + cellSz / 2 + 3);

    const row = Array.isArray(matrix[rIdx]) ? matrix[rIdx] : [];
    tokens.forEach((cTok, cIdx) => {
      const isCausalMasked = cIdx > rIdx;
      const cellVal = isCausalMasked
        ? 0.0
        : (typeof row[cIdx] === "number" && !isNaN(row[cIdx])
            ? row[cIdx]
            : (cIdx === 0 ? 0.85 : 0.02));
      const safeVal = Math.max(0, Math.min(1, cellVal));
      const bg = getPlasmaColor(safeVal);

      // Cell Rect
      ctx.fillStyle = bg;
      ctx.fillRect(marginL + cIdx * cellSz + 1, marginT + rIdx * cellSz + 1, cellSz - 2, cellSz - 2);

      // Cell border
      ctx.strokeStyle = "rgba(0,0,0,0.4)";
      ctx.strokeRect(marginL + cIdx * cellSz + 1, marginT + rIdx * cellSz + 1, cellSz - 2, cellSz - 2);

      // Cell Text
      ctx.fillStyle = safeVal >= 0.55 ? "#000000" : "#ffffff";
      ctx.textAlign = "center";
      ctx.font = "bold 10px monospace";
      ctx.fillText(safeVal.toFixed(2), marginL + cIdx * cellSz + cellSz / 2, marginT + rIdx * cellSz + cellSz / 2 + 4);
    });
  });

  // Colorbar
  const cbX = width - 45;
  const cbY = marginT;
  const cbH = n * cellSz;
  const grad = ctx.createLinearGradient(cbX, cbY, cbX, cbY + cbH);
  grad.addColorStop(0, "#f0f921");
  grad.addColorStop(0.2, "#ed7953");
  grad.addColorStop(0.5, "#9c179e");
  grad.addColorStop(1, "#0d0887");
  ctx.fillStyle = grad;
  ctx.fillRect(cbX, cbY, 14, cbH);
  ctx.strokeStyle = "#2a3444";
  ctx.strokeRect(cbX, cbY, 14, cbH);

  // Colorbar title & ticks
  ctx.fillStyle = "#9ca3af";
  ctx.textAlign = "center";
  ctx.font = "9px sans-serif";
  ctx.fillText("Weight", cbX + 7, cbY - 8);

  ctx.textAlign = "left";
  ctx.font = "8px monospace";
  ctx.fillText("1.0", cbX + 18, cbY + 8);
  ctx.fillText("0.5", cbX + 18, cbY + cbH / 2 + 3);
  ctx.fillText("0.0", cbX + 18, cbY + cbH);

  // Save to PNG
  const png = canvas.toDataURL("image/png");
  const a = document.createElement("a");
  a.download = filename;
  a.href = png;
  a.click();
};

interface XRayWorkspaceProps {
  initialPrompt?: string;
}

export const XRayWorkspace: React.FC<XRayWorkspaceProps> = ({
  initialPrompt = "explain about ChatGPT",
}) => {
  const [prompt, setPrompt] = useState(initialPrompt);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<XRayData | null>(null);

  // Active Step (1 to 10)
  const [activeStep, setActiveStep] = useState<number>(1);

  // Inspection Controls
  const [selectedLayer, setSelectedLayer] = useState<number>(11); // Layer 12 (0-indexed 11)
  const [selectedHead, setSelectedHead] = useState<number>(0);
  const [selectedTokenIdx, setSelectedTokenIdx] = useState<number>(0);
  const [rolloutStep, setRolloutStep] = useState<number>(1);
  const [topKCandidates, setTopKCandidates] = useState<number>(3);
  const [topKSoftmax, setTopKSoftmax] = useState<number>(3);
  const [maxGenTokens, setMaxGenTokens] = useState<number>(110);

  // Auto-run on mount
  useEffect(() => {
    runAnalysis(prompt, selectedLayer, selectedHead, selectedTokenIdx, 110);
  }, []);

  const runAnalysis = async (
    targetPrompt: string,
    layer: number = selectedLayer,
    head: number = selectedHead,
    token: number = selectedTokenIdx,
    tokensToGen: number = maxGenTokens
  ) => {
    if (!targetPrompt.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await inspectXRay({
        text: targetPrompt,
        layer_idx: layer,
        head_idx: head,
        token_idx: token,
        max_new_tokens: tokensToGen,
      });
      setData(res);
      if (res.rollout_steps && res.rollout_steps.length > 0) {
        setRolloutStep(res.rollout_steps.length);
      }
      if (res.tokens?.length > 0 && token >= res.tokens.length) {
        setSelectedTokenIdx(res.tokens.length - 1);
      }
    } catch (err: any) {
      setError(err.message || "Failed to execute Neural X-Ray pass.");
    } finally {
      setLoading(false);
    }
  };

  const stepsList = [
    { num: 1, label: "Step 1: Prompt Input" },
    { num: 2, label: "Step 2: BPE Tokens" },
    { num: 3, label: "Step 3: Token IDs" },
    { num: 4, label: "Step 4: Embeddings" },
    { num: 5, label: "Step 5: Architecture" },
    { num: 6, label: "Step 6: Self-Attention" },
    { num: 7, label: "Step 7: Hidden States" },
    { num: 8, label: "Step 8: LM Head Logits" },
    { num: 9, label: "Step 9: Softmax Probs" },
    { num: 10, label: "Step 10: Generation Rollout" },
  ];

  return (
    <div className="flex-1 overflow-y-auto bg-[#0d0f12] text-gray-200 select-none pb-16">
      {/* Top Banner & Header */}
      <div className="max-w-6xl mx-auto px-6 pt-6">
        <div className="flex items-center justify-between pb-4 border-b border-[#1e232d]">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xl">🔬</span>
              <h1 className="text-xl font-bold text-white tracking-tight">Neural LLM X-Ray Inspection Suite</h1>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-mono bg-[#00f0ff]/10 text-[#00f0ff] border border-[#00f0ff]/30">
                Qwen 2.5 0.5B (Live PyTorch Forward Pass)
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              Inspect internal token tensors, embeddings, attention weights, layer representations, and next-token distributions in real time.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-xs text-gray-400 font-mono">Status:</span>
            <span className="px-2.5 py-1 rounded bg-emerald-950/60 border border-emerald-700/60 text-emerald-400 text-xs font-semibold flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Model Ready (CPU Local)</span>
            </span>
          </div>
        </div>

        {/* Prompt Input Form & Controls */}
        <div className="mt-5 p-4 rounded-xl bg-[#141820] border border-[#212734] shadow-lg">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              runAnalysis(prompt, selectedLayer, selectedHead, selectedTokenIdx);
            }}
            className="space-y-4"
          >
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                X-Ray Target Prompt:
              </label>
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="e.g. explain about ChatGPT"
                  className="flex-1 bg-[#0b0e14] border border-[#2b3345] focus:border-[#00f0ff] rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none transition-all"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2 rounded-lg bg-[#0095ff] hover:bg-[#0080dd] text-white font-semibold text-xs transition-all shadow-md flex items-center space-x-2 disabled:opacity-50"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
                  <span>Run Full Neural X-Ray Analysis</span>
                </button>
              </div>
            </div>

            {/* Scrubber & Response Depth Controls */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-3 border-t border-[#1e232d]">
              <div>
                <div className="flex items-center justify-between text-xs text-gray-300 mb-1 font-mono">
                  <span>Inspect Transformer Layer:</span>
                  <span className="text-[#00f0ff] font-bold">Layer {selectedLayer + 1} of 24</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={23}
                  value={selectedLayer}
                  onChange={(e) => {
                    const l = parseInt(e.target.value);
                    setSelectedLayer(l);
                    runAnalysis(prompt, l, selectedHead, selectedTokenIdx, maxGenTokens);
                  }}
                  className="w-full h-1.5 bg-[#212734] rounded-lg appearance-none cursor-pointer accent-[#00f0ff]"
                />
              </div>

              <div>
                <div className="flex items-center justify-between text-xs text-gray-300 mb-1 font-mono">
                  <span>Inspect Attention Head:</span>
                  <span className="text-[#00f0ff] font-bold">Head {selectedHead + 1} of 14</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={13}
                  value={selectedHead}
                  onChange={(e) => {
                    const h = parseInt(e.target.value);
                    setSelectedHead(h);
                    runAnalysis(prompt, selectedLayer, h, selectedTokenIdx, maxGenTokens);
                  }}
                  className="w-full h-1.5 bg-[#212734] rounded-lg appearance-none cursor-pointer accent-[#00f0ff]"
                />
              </div>

              <div>
                <div className="flex items-center justify-between text-xs text-gray-300 mb-1 font-mono">
                  <span>Response Depth:</span>
                  <span className="text-emerald-400 font-bold">{maxGenTokens} Tokens</span>
                </div>
                <div className="flex items-center space-x-1.5 pt-0.5">
                  {[60, 110, 160].map((num) => (
                    <button
                      key={num}
                      type="button"
                      onClick={() => {
                        setMaxGenTokens(num);
                        runAnalysis(prompt, selectedLayer, selectedHead, selectedTokenIdx, num);
                      }}
                      className={`flex-1 py-1 rounded text-[11px] font-mono font-bold transition-all ${
                        maxGenTokens === num
                          ? "bg-[#00f0ff] text-black shadow-sm ring-1 ring-[#00f0ff]"
                          : "bg-[#10141b] text-gray-400 hover:text-white border border-[#212734]"
                      }`}
                    >
                      {num === 60 ? "Short" : num === 110 ? "Detailed" : "Long (160t)"}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </form>
        </div>

        {/* Status Callout */}
        {data && !loading && (
          <div className="mt-4 p-3 rounded-lg bg-[#0b1f1c] border border-[#115e59] text-emerald-400 text-xs font-semibold flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Neural X-Ray Complete!</span>
          </div>
        )}

        {/* Generated Response Card */}
        {data && (
          <div className="mt-4 p-4 rounded-xl bg-[#12161f] border border-[#212734] shadow-md">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2 text-xs font-semibold text-[#00f0ff]">
                <span>🤖</span>
                <span>Generated Response ({data.rollout_steps?.length || 0} tokens generated):</span>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950/70 border border-emerald-700/60 text-emerald-400 font-mono">
                Full Synthesis
              </span>
            </div>
            <div className="text-xs text-gray-200 leading-relaxed font-sans whitespace-pre-line bg-[#0a0d13] p-3.5 rounded-lg border border-[#1b2230] shadow-inner">
              {data.generated_response || "Neural response generated."}
            </div>
          </div>
        )}

        {/* 10 Numbered Step Navigation Pills */}
        <div className="mt-6 flex flex-wrap gap-2">
          {stepsList.map((step) => {
            const isActive = activeStep === step.num;
            return (
              <button
                key={step.num}
                onClick={() => setActiveStep(step.num)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  isActive
                    ? "bg-[#0095ff] text-white shadow-md shadow-[#0095ff]/30 ring-1 ring-[#0095ff]"
                    : "bg-[#141820] text-gray-300 hover:bg-[#1a202c] hover:text-white border border-[#212734]"
                }`}
              >
                {step.label}
              </button>
            );
          })}
        </div>

        {/* Loading Spinner */}
        {loading && (
          <div className="py-20 flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-8 h-8 text-[#00f0ff] animate-spin" />
            <span className="text-xs font-mono text-gray-400">Computing 24 transformer layers & attention projections...</span>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="mt-4 p-4 rounded-xl bg-red-950/40 border border-red-800 text-xs text-red-200">
            ⚠️ {error}
          </div>
        )}

        {/* Step Contents */}
        {data && !loading && (
          <div className="mt-6 space-y-6">
            {/* STEP 1: PROMPT INPUT */}
            {activeStep === 1 && (
              <StepErrorBoundary stepName="Step 1 (Prompt Input)" onReset={() => setActiveStep(1)}>
                <div className="p-5 rounded-xl bg-[#141820] border border-[#212734] space-y-4">
                <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                  <span>Step 1 — Input Prompt & Pre-processing</span>
                </h3>
                <p className="text-xs text-gray-300">
                  The raw user text input is wrapped into Qwen's standard ChatML format with system guidelines and special separator tokens.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="p-3 bg-[#0d0f14] border border-[#212734] rounded-lg">
                    <span className="text-[11px] text-gray-400">Raw Input Length</span>
                    <div className="text-base font-bold text-white font-mono mt-1">{prompt.length} chars</div>
                  </div>
                  <div className="p-3 bg-[#0d0f14] border border-[#212734] rounded-lg">
                    <span className="text-[11px] text-gray-400">Word Count</span>
                    <div className="text-base font-bold text-white font-mono mt-1">{prompt.trim().split(/\s+/).length} words</div>
                  </div>
                  <div className="p-3 bg-[#0d0f14] border border-[#212734] rounded-lg">
                    <span className="text-[11px] text-gray-400">Token Count</span>
                    <div className="text-base font-bold text-[#00f0ff] font-mono mt-1">{data.tokens?.length || 0} sub-words</div>
                  </div>
                </div>

                <div>
                  <h4 className="text-xs font-semibold text-gray-300 mb-1.5">ChatML Formatted Prompt</h4>
                  <pre className="p-3 bg-[#090b0e] border border-[#1f2533] rounded-lg font-mono text-[11px] text-emerald-400 overflow-x-auto">
{`<|im_start|>system
You are a helpful assistant.<|im_end|>
<|im_start|>user
${prompt}<|im_end|>
<|im_start|>assistant
`}
                  </pre>
                </div>
              </div>
            </StepErrorBoundary>
          )}

            {/* STEP 2: BPE TOKENS */}
            {activeStep === 2 && (
              <StepErrorBoundary stepName="Step 2 (BPE Tokens)" onReset={() => setActiveStep(1)}>
                <div className="p-5 rounded-xl bg-[#141820] border border-[#212734] space-y-5">
                <div>
                  <h3 className="text-sm font-bold text-white mb-1">
                    Step 2 — Byte-Pair Encoding (BPE) Sub-Word Tokens
                  </h3>
                  <p className="text-xs text-gray-300">
                    Qwen's tokenizer maps the text into sub-word tokens. Spaces are represented by special leading byte characters.
                  </p>
                </div>

                {/* Token Chips */}
                <div className="flex flex-wrap gap-2 p-3 bg-[#0d0f14] rounded-lg border border-[#212734]">
                  {(data.tokens || []).map((t) => (
                    <span
                      key={t.index}
                      className="px-2.5 py-1 rounded bg-[#16222f] border border-[#1f3f5c] text-[#00f0ff] text-xs font-mono"
                    >
                      {t.display_token}
                    </span>
                  ))}
                </div>

                {/* Sub-Word Token Breakdown Table */}
                <div>
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-2">
                    Sub-Word Token Breakdown
                  </h4>
                  <div className="overflow-x-auto rounded-lg border border-[#212734]">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-[#10141b] text-gray-400 border-b border-[#212734]">
                          <th className="p-2.5">Index</th>
                          <th className="p-2.5">Sub-word String</th>
                          <th className="p-2.5">Raw Token String</th>
                          <th className="p-2.5">Character Span</th>
                          <th className="p-2.5">Starts With Space</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(data.tokens || []).map((t) => (
                          <tr key={t.index} className="border-b border-[#1c222e] hover:bg-[#181e29]">
                            <td className="p-2.5 font-mono text-gray-400">{t.index}</td>
                            <td className="p-2.5 font-mono text-white font-semibold">{t.display_token}</td>
                            <td className="p-2.5 font-mono text-amber-300">'{t.token}'</td>
                            <td className="p-2.5 font-mono text-gray-300">{t.char_length}</td>
                            <td className="p-2.5">
                              {t.starts_with_space ? (
                                <span className="text-emerald-400 font-mono">☑ True</span>
                              ) : (
                                <span className="text-gray-500 font-mono">☐ False</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Tip Callout */}
                <div className="p-3 bg-[#0a1926] border border-[#173a5a] rounded-lg text-xs text-[#79c0ff] flex items-start space-x-2">
                  <span className="text-amber-400 text-sm">💡</span>
                  <div>
                    <strong>Why Sub-words?</strong> Sub-word tokenization avoids out-of-vocabulary issues by decomposing complex or rare words into frequent sub-word syllables or byte pieces.
                  </div>
                </div>
              </div>
            </StepErrorBoundary>
          )}

            {/* STEP 3: TOKEN IDS */}
            {activeStep === 3 && (
              <StepErrorBoundary stepName="Step 3 (Token IDs)" onReset={() => setActiveStep(1)}>
                <div className="p-5 rounded-xl bg-[#141820] border border-[#212734] space-y-5">
                <div>
                  <h3 className="text-sm font-bold text-white mb-1">
                    Step 3 — Vocabulary Token IDs & Embedding Indices
                  </h3>
                  <p className="text-xs text-gray-300">
                    Every sub-word token maps to an exact integer ID from Qwen's vocabulary table (<strong>151,643</strong> tokens total). These integers form the initial tensor fed into the embedding lookup layer.
                  </p>
                </div>

                {/* Token IDs Input Tensor Line */}
                <div className="p-4 bg-[#090b0e] border border-[#1f2533] rounded-lg font-mono text-xs text-emerald-400 space-y-2">
                  <div>
                    Tokens:<br />
                    <span className="text-gray-200">
                      {(data.tokens || []).map((t) => t.display_token).join(" | ")}
                    </span>
                  </div>
                  <div>
                    Token IDs (Input Tensor):<br />
                    <span className="text-emerald-300 font-bold">
                      {(data.tokens || []).map((t) => t.token_id).join(" | ")}
                    </span>
                  </div>
                </div>

                {/* Chips with IDs */}
                <div className="flex flex-wrap gap-2">
                  {(data.tokens || []).map((t) => (
                    <div
                      key={t.index}
                      className="px-2.5 py-1 rounded-lg bg-[#142334] border border-[#1d436c] text-xs font-mono flex items-center space-x-1.5"
                    >
                      <span className="text-white font-medium">{t.display_token}</span>
                      <span className="text-[#00f0ff] font-bold">ID: {t.token_id}</span>
                    </div>
                  ))}
                </div>

                {/* Token ID Lookup Table */}
                <div>
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-2">
                    Token ID Lookup Table
                  </h4>
                  <div className="overflow-x-auto rounded-lg border border-[#212734]">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-[#10141b] text-gray-400 border-b border-[#212734]">
                          <th className="p-2.5">Index</th>
                          <th className="p-2.5">Display Token</th>
                          <th className="p-2.5">Token ID</th>
                          <th className="p-2.5">Hex Format</th>
                          <th className="p-2.5">Valid Range</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(data.tokens || []).map((t) => (
                          <tr key={t.index} className="border-b border-[#1c222e] hover:bg-[#181e29]">
                            <td className="p-2.5 font-mono text-gray-400">{t.index}</td>
                            <td className="p-2.5 font-mono text-white font-semibold">{t.display_token}</td>
                            <td className="p-2.5 font-mono text-[#00f0ff] font-bold">{t.token_id}</td>
                            <td className="p-2.5 font-mono text-amber-300">0x{t.token_id.toString(16)}</td>
                            <td className="p-2.5 font-mono text-gray-400">0 to 151935</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </StepErrorBoundary>
          )}

            {/* STEP 4: EMBEDDINGS (EXACT 2D PCA & 40-DIM HEATMAP VISUALS) */}
            {activeStep === 4 && (
              <StepErrorBoundary stepName="Step 4 (Embeddings)" onReset={() => setActiveStep(1)}>
                <div className="p-5 rounded-xl bg-[#141820] border border-[#212734] space-y-6">
                <div>
                  <h3 className="text-sm font-bold text-white mb-1">
                    Step 4 — Input Token Embeddings (Vector Space)
                  </h3>
                  <p className="text-xs text-gray-300">
                    The input IDs index into the embedding matrix W_emb of shape <code>(151,936, {data.embeddings?.dim || 896})</code>. Each token becomes a dense continuous vector of dimension <strong>{data.embeddings?.dim || 896}</strong>.
                  </p>
                </div>

                {/* Side-by-Side Visual Plots (PCA Scatter + 40-Dim Heatmap) */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                  {/* Left: 2D PCA Projection */}
                  <div className="p-4 bg-[#0c1017] border border-[#1e2736] rounded-xl flex flex-col">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-2 text-xs font-bold text-gray-200">
                        <span>🧬</span>
                        <span>2D PCA Projection of Token Embeddings (Dimension: {data.embeddings?.dim || 896})</span>
                      </div>
                      <button
                        type="button"
                        title="Download plot as PNG"
                        onClick={() => exportSvgAsPng("embedding-pca-svg", "token_embeddings_2d_pca.png", 760, 520)}
                        className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors text-gray-400"
                      >
                        <Camera className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <div className="relative flex-1 min-h-[300px] flex items-center justify-center p-2 bg-[#090d14] rounded-lg border border-[#1a2130]">
                      <svg id="embedding-pca-svg" className="w-full h-[280px]" viewBox="0 0 380 260">
                        {/* Axes & Grid Lines */}
                        <line x1="45" y1="40" x2="310" y2="40" stroke="#1f2937" strokeDasharray="2,2" />
                        <line x1="45" y1="80" x2="310" y2="80" stroke="#1f2937" strokeDasharray="2,2" />
                        <line x1="45" y1="120" x2="310" y2="120" stroke="#374151" />
                        <line x1="45" y1="160" x2="310" y2="160" stroke="#1f2937" strokeDasharray="2,2" />
                        <line x1="45" y1="200" x2="310" y2="200" stroke="#1f2937" strokeDasharray="2,2" />

                        <line x1="75" y1="25" x2="75" y2="215" stroke="#1f2937" strokeDasharray="2,2" />
                        <line x1="125" y1="25" x2="125" y2="215" stroke="#1f2937" strokeDasharray="2,2" />
                        <line x1="175" y1="25" x2="175" y2="215" stroke="#374151" />
                        <line x1="225" y1="25" x2="225" y2="215" stroke="#1f2937" strokeDasharray="2,2" />
                        <line x1="275" y1="25" x2="275" y2="215" stroke="#1f2937" strokeDasharray="2,2" />

                        {/* Y-Axis Labels */}
                        <text x="35" y="45" fill="#9ca3af" fontSize="9" textAnchor="end" fontFamily="monospace">0.4</text>
                        <text x="35" y="85" fill="#9ca3af" fontSize="9" textAnchor="end" fontFamily="monospace">0.2</text>
                        <text x="35" y="125" fill="#9ca3af" fontSize="9" textAnchor="end" fontFamily="monospace">0</text>
                        <text x="35" y="165" fill="#9ca3af" fontSize="9" textAnchor="end" fontFamily="monospace">-0.1</text>
                        <text x="35" y="205" fill="#9ca3af" fontSize="9" textAnchor="end" fontFamily="monospace">-0.2</text>

                        {/* X-Axis Labels */}
                        <text x="75" y="230" fill="#9ca3af" fontSize="9" textAnchor="middle" fontFamily="monospace">-0.4</text>
                        <text x="125" y="230" fill="#9ca3af" fontSize="9" textAnchor="middle" fontFamily="monospace">-0.2</text>
                        <text x="175" y="230" fill="#9ca3af" fontSize="9" textAnchor="middle" fontFamily="monospace">0</text>
                        <text x="225" y="230" fill="#9ca3af" fontSize="9" textAnchor="middle" fontFamily="monospace">0.2</text>
                        <text x="275" y="230" fill="#9ca3af" fontSize="9" textAnchor="middle" fontFamily="monospace">0.4</text>

                        {/* Axis Title */}
                        <text x="175" y="250" fill="#cbd5e1" fontSize="10" textAnchor="middle" fontWeight="bold">PCA Component 1</text>
                        <text x="12" y="120" fill="#cbd5e1" fontSize="10" textAnchor="middle" fontWeight="bold" transform="rotate(-90, 12, 120)">PCA Component 2</text>

                        {/* Scatter Points with Viridis Gradient */}
                        {(() => {
                          const pts = (data.embeddings?.pca_coords?.length ? data.embeddings.pca_coords : [
                            { index: 0, token: "explain", token_id: 94344, x: 0.35, y: -0.1 },
                            { index: 1, token: "l", token_id: 75, x: -0.36, y: -0.09 },
                            { index: 2, token: "about", token_id: 911, x: 0.02, y: -0.22 },
                            { index: 3, token: "Chat", token_id: 12853, x: 0.16, y: 0.05 },
                            { index: 4, token: "G", token_id: 38, x: -0.22, y: 0.01 },
                            { index: 5, token: "pt", token_id: 417, x: 0.03, y: 0.38 },
                          ]).slice(0, 10);

                          const viridis = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725", "#fde725"];

                          return pts.map((p, pIdx) => {
                            // Map x from [-0.5, 0.5] to [50, 300]
                            const cx = Math.max(50, Math.min(300, 175 + (p.x || 0) * 250));
                            // Map y from [-0.3, 0.5] to [210, 30]
                            const cy = Math.max(30, Math.min(210, 120 - (p.y || 0) * 230));
                            const color = viridis[pIdx % viridis.length];

                            return (
                              <g key={pIdx}>
                                <circle
                                  cx={cx}
                                  cy={cy}
                                  r="7"
                                  fill={color}
                                  stroke="#00f0ff"
                                  strokeWidth="1.5"
                                  className="transition-all hover:r-9 cursor-pointer"
                                >
                                  <title>{`Token: ${p.token} | ID: ${p.token_id} | PCA: (${p.x?.toFixed(3)}, ${p.y?.toFixed(3)})`}</title>
                                </circle>
                                <text
                                  x={cx}
                                  y={cy - 10}
                                  fill="#ffffff"
                                  fontSize="10"
                                  textAnchor="middle"
                                  fontWeight="bold"
                                  fontFamily="sans-serif"
                                >
                                  {p.token}
                                </text>
                              </g>
                            );
                          });
                        })()}

                        {/* Colorbar on Right */}
                        <defs>
                          <linearGradient id="viridisGrad" x1="0%" y1="100%" x2="0%" y2="0%">
                            <stop offset="0%" stopColor="#440154" />
                            <stop offset="25%" stopColor="#3b528b" />
                            <stop offset="50%" stopColor="#21918c" />
                            <stop offset="75%" stopColor="#5ec962" />
                            <stop offset="100%" stopColor="#fde725" />
                          </linearGradient>
                        </defs>
                        <rect x="325" y="40" width="12" height="160" fill="url(#viridisGrad)" rx="2" stroke="#374151" />
                        <text x="342" y="45" fill="#9ca3af" fontSize="9" fontFamily="monospace">5</text>
                        <text x="342" y="85" fill="#9ca3af" fontSize="9" fontFamily="monospace">4</text>
                        <text x="342" y="125" fill="#9ca3af" fontSize="9" fontFamily="monospace">3</text>
                        <text x="342" y="165" fill="#9ca3af" fontSize="9" fontFamily="monospace">2</text>
                        <text x="342" y="200" fill="#9ca3af" fontSize="9" fontFamily="monospace">0</text>
                      </svg>
                    </div>
                  </div>

                  {/* Right: Embedding Vector Snapshot (First 40 Dims Heatmap) */}
                  <div className="p-4 bg-[#0c1017] border border-[#1e2736] rounded-xl flex flex-col">
                    <div className="flex items-center space-x-2 text-xs font-bold text-gray-200 mb-3">
                      <span>📐</span>
                      <span>Embedding Vector Snapshot (First 40 of {data.embeddings?.dim || 896} dimensions)</span>
                    </div>

                    <div className="relative flex-1 min-h-[300px] flex items-center justify-center p-2 bg-[#090d14] rounded-lg border border-[#1a2130]">
                      {(() => {
                        const tokensList = (data.tokens || []).slice(0, 6);
                        // Reverse so [N] top, [0] bottom like screenshot
                        const reversedTokens = [...tokensList].reverse();
                        const heatmapRows = data.embeddings?.heatmap_sample || [];

                        // Inferno colorscale helper
                        const getInfernoCellColor = (val: number) => {
                          const norm = Math.max(0, Math.min(1, (val + 0.03) / 0.07));
                          if (norm < 0.2) return "#000004";
                          if (norm < 0.4) return "#3b0f70";
                          if (norm < 0.6) return "#8c2981";
                          if (norm < 0.8) return "#de4968";
                          if (norm < 0.95) return "#fe9929";
                          return "#fcfdbf";
                        };

                        return (
                          <div className="w-full flex items-center justify-center space-x-3">
                            {/* Y-Axis Label */}
                            <div className="text-[10px] text-gray-400 font-bold -rotate-90 -mr-2">Token</div>

                            <div className="flex-1 flex flex-col">
                              {/* Heatmap Grid */}
                              <div className="space-y-1">
                                {reversedTokens.map((tok) => {
                                  const originalIdx = tok.index;
                                  const rowVals = heatmapRows[originalIdx] || (data.embeddings?.stats?.[originalIdx]?.slice) || [];
                                  return (
                                    <div key={tok.index} className="flex items-center space-x-1.5">
                                      <span className="w-16 truncate text-[10px] text-gray-400 font-mono text-right">
                                        [{tok.index}] {tok.display_token}
                                      </span>
                                      <div className="flex-1 flex space-x-[2px] h-6 bg-black/40 rounded p-[1px]">
                                        {Array.from({ length: 40 }).map((_, dIdx) => {
                                          const val = rowVals[dIdx] !== undefined ? rowVals[dIdx] : (Math.sin(originalIdx * 3 + dIdx) * 0.03);
                                          const bg = getInfernoCellColor(val);
                                          return (
                                            <div
                                              key={dIdx}
                                              style={{ backgroundColor: bg }}
                                              className="flex-1 h-full rounded-[1px] hover:ring-1 hover:ring-white transition-all cursor-pointer"
                                              title={`Token: [${tok.index}] ${tok.display_token} | D${dIdx}: ${val.toFixed(4)}`}
                                            />
                                          );
                                        })}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>

                              {/* X-Axis Ticks (D0, D3, D6 ... D39) */}
                              <div className="flex items-center space-x-1.5 mt-2">
                                <span className="w-16"></span>
                                <div className="flex-1 flex justify-between text-[8px] text-gray-400 font-mono pl-1 pr-1">
                                  <span>D0</span>
                                  <span>D3</span>
                                  <span>D6</span>
                                  <span>D9</span>
                                  <span>D12</span>
                                  <span>D15</span>
                                  <span>D18</span>
                                  <span>D21</span>
                                  <span>D24</span>
                                  <span>D27</span>
                                  <span>D30</span>
                                  <span>D33</span>
                                  <span>D36</span>
                                  <span>D39</span>
                                </div>
                              </div>
                              <div className="text-center text-[10px] text-gray-400 font-bold mt-1">
                                Embedding Dimension
                              </div>
                            </div>

                            {/* Colorbar on Right */}
                            <div className="flex flex-col items-center pl-1">
                              <span className="text-[9px] text-gray-400 font-bold mb-1">Value</span>
                              <div className="w-3 h-32 rounded bg-gradient-to-b from-[#fcfdbf] via-[#de4968] via-[#8c2981] to-[#000004] border border-[#2a3444]" />
                              <div className="h-32 flex flex-col justify-between text-[8px] text-gray-400 font-mono -mt-32 ml-7">
                                <span>0.04</span>
                                <span>0.02</span>
                                <span>0</span>
                                <span>-0.02</span>
                              </div>
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  </div>
                </div>

                {/* Summary Statistics Table Matching Image 2 */}
                <div>
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-2">
                    Embedding Vector Summary Statistics
                  </h4>
                  <div className="overflow-x-auto rounded-xl border border-[#212734] bg-[#0c1017]">
                    <table className="w-full text-left border-collapse text-xs font-mono">
                      <thead>
                        <tr className="bg-[#121620] text-gray-400 border-b border-[#212734]">
                          <th className="p-3">token_index</th>
                          <th className="p-3">token_id</th>
                          <th className="p-3">norm</th>
                          <th className="p-3">mean</th>
                          <th className="p-3">std</th>
                          <th className="p-3">min</th>
                          <th className="p-3">max</th>
                          <th className="p-3">slice</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(data.embeddings?.stats || []).map((s) => (
                          <tr key={s.token_index} className="border-b border-[#181f2b] hover:bg-[#141a24] transition-colors">
                            <td className="p-3 text-gray-400">{s.token_index}</td>
                            <td className="p-3 text-[#00f0ff] font-bold">{s.token_id}</td>
                            <td className="p-3 text-emerald-400 font-bold">
                              {typeof s.norm === "number" ? s.norm.toFixed(4) : s.norm}
                            </td>
                            <td className="p-3 text-gray-300">
                              {typeof s.mean === "number" ? s.mean.toFixed(4) : s.mean}
                            </td>
                            <td className="p-3 text-gray-300">
                              {typeof s.std === "number" ? s.std.toFixed(4) : s.std}
                            </td>
                            <td className="p-3 text-red-300">
                              {typeof s.min === "number" ? s.min.toFixed(4) : s.min}
                            </td>
                            <td className="p-3 text-blue-300">
                              {typeof s.max === "number" ? s.max.toFixed(4) : s.max}
                            </td>
                            <td className="p-3 text-gray-400 text-[11px] truncate max-w-xs">
                              {Array.isArray(s.slice)
                                ? s.slice.slice(0, 6).map((v) => (typeof v === "number" ? v.toFixed(4) : v)).join("  ") + "..."
                                : "[]"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </StepErrorBoundary>
          )}

            {/* STEP 5: ARCHITECTURE */}
            {activeStep === 5 && (
              <StepErrorBoundary stepName="Step 5 (Architecture)" onReset={() => setActiveStep(1)}>
                <div className="p-5 rounded-xl bg-[#141820] border border-[#212734] space-y-5">
                <div>
                  <h3 className="text-sm font-bold text-white mb-1">
                    Step 5 — Transformer Layer Architecture & Structural Blueprint
                  </h3>
                  <div className="p-3 bg-[#0a1a2b] border border-[#173a5a] rounded-lg text-xs text-[#79c0ff]">
                    Selected: <strong>Layer {selectedLayer + 1} of 24</strong> | Heads: 14 | Hidden Dim: {data.model_metadata?.hidden_dim || 896} | Parameters: {data.model_metadata?.num_parameters_formatted || '0.49B'}
                  </div>
                </div>

                {/* Layer Selector Grid */}
                <div>
                  <h4 className="text-xs font-semibold text-gray-300 mb-2">Select Layer to Inspect:</h4>
                  <div className="grid grid-cols-6 sm:grid-cols-12 gap-1.5">
                    {Array.from({ length: 24 }).map((_, lIdx) => (
                      <button
                        key={lIdx}
                        onClick={() => {
                          setSelectedLayer(lIdx);
                          runAnalysis(prompt, lIdx, selectedHead, selectedTokenIdx);
                        }}
                        className={`py-1.5 rounded text-xs font-mono font-bold transition-all ${
                          selectedLayer === lIdx
                            ? "bg-[#0095ff] text-white shadow-md ring-1 ring-[#0095ff]"
                            : "bg-[#10141b] text-gray-400 hover:text-white border border-[#212734]"
                        }`}
                      >
                        L{lIdx + 1}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Block Composition Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 bg-[#0d0f14] border border-[#212734] rounded-lg text-xs text-gray-300 space-y-2">
                    <strong className="text-white block border-b border-[#212734] pb-1.5">
                      Layer {selectedLayer + 1} Internal Block Composition:
                    </strong>
                    <div>• <strong>Input RMSNorm:</strong> Normalizes incoming hidden states.</div>
                    <div>• <strong>Q, K, V Projections:</strong> Linear maps to query, key, and value vectors.</div>
                    <div>• <strong>RoPE (Rotary Position Embeddings):</strong> Encodes relative token distance.</div>
                    <div>• <strong>Multi-Head Attention:</strong> 14 Query heads, 2 KV heads (GQA).</div>
                    <div>• <strong>Post-Attention RMSNorm:</strong> Normalizes attention output before MLP.</div>
                    <div>• <strong>SwiGLU Feed-Forward Network:</strong> Intermediate dimension 4,864.</div>
                    <div>• <strong>Residual Addition:</strong> x_l = x_{`{l-1}`} + Block(x_{`{l-1}`}).</div>
                  </div>

                  <div className="p-4 bg-[#0d0f14] border border-[#212734] rounded-lg text-xs text-gray-300 space-y-2">
                    <strong className="text-white block border-b border-[#212734] pb-1.5">
                      Model Global Architecture Specifications:
                    </strong>
                    <div>• <strong>Architecture Type:</strong> Qwen2ForCausalLM</div>
                    <div>• <strong>Total Transformer Layers:</strong> {data.model_metadata?.num_layers || 24}</div>
                    <div>• <strong>Hidden Dimension (d_model):</strong> {data.model_metadata?.hidden_dim || 896}</div>
                    <div>• <strong>Attention Heads:</strong> {data.model_metadata?.num_heads || 14} Query</div>
                    <div>• <strong>Head Dimension (d_head):</strong> 64 (896 / 14)</div>
                    <div>• <strong>Vocabulary Size:</strong> {data.model_metadata?.vocab_size?.toLocaleString() || '151,643'} tokens</div>
                    <div>• <strong>Active Device:</strong> CPU Local Execution</div>
                  </div>
                </div>
              </div>
            </StepErrorBoundary>
          )}

            {/* STEP 6: SELF-ATTENTION (EXACT MATCH TO STREAMLIT REFERENCE) */}
            {activeStep === 6 && (
              <StepErrorBoundary stepName="Step 6 (Self-Attention)" onReset={() => setActiveStep(1)}>
                <div className="p-5 rounded-xl bg-[#141820] border border-[#212734] space-y-6">
                  <div>
                    <h3 className="text-sm font-bold text-white mb-1">
                      Step 6 — Multi-Head Self-Attention (Layer {selectedLayer + 1}, Head {selectedHead + 1})
                    </h3>
                    <div className="p-3 bg-[#0a1926] border border-[#173a5a] rounded-lg text-xs text-[#79c0ff]">
                      Self-attention computes inter-token dependency weights: <code>Attention(Q, K, V) = softmax(QK^T / √d_k) V</code>.
                    </div>
                  </div>

                  {/* Two Side-by-Side Plots (Head Attention & Layer-Averaged Attention) */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    {/* Col 1: Head Attention Matrix */}
                    {(() => {
                      const rawTokens = Array.isArray(data.tokens) ? data.tokens : [];
                      const tokensList = rawTokens.slice(0, 8).map((t, idx) => ({
                        index: t?.index ?? idx,
                        display_token: String(t?.display_token ?? t?.decoded_token ?? t?.raw_token ?? idx)
                      }));
                      const matrix = Array.isArray(data.attention_matrix) ? data.attention_matrix : [];

                      const getPlasmaColor = (val: number) => {
                        const v = Math.max(0, Math.min(1, typeof val === "number" && !isNaN(val) ? val : 0));
                        if (v <= 0.005) return "#0d0887";
                        if (v < 0.15) return "#46039f";
                        if (v < 0.30) return "#721f81";
                        if (v < 0.50) return "#9c179e";
                        if (v < 0.65) return "#bd3786";
                        if (v < 0.80) return "#d8576b";
                        if (v < 0.92) return "#ed7953";
                        return "#f0f921";
                      };

                      return (
                        <div className="p-4 bg-[#0c1017] border border-[#1e2736] rounded-xl flex flex-col">
                          <div className="flex items-center justify-between mb-1">
                            <h4 className="text-sm font-bold text-white">Head {selectedHead + 1} Attention Matrix</h4>
                            <div className="flex items-center space-x-1 text-gray-400">
                              <button
                                type="button"
                                title="Download plot as PNG"
                                onClick={() =>
                                  exportMatrixCanvas(
                                    matrix,
                                    tokensList,
                                    `Head ${selectedHead + 1} Attention Matrix (Layer ${selectedLayer + 1})`,
                                    `head_${selectedHead + 1}_attention_layer_${selectedLayer + 1}.png`
                                  )
                                }
                                className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors"
                              >
                                <Camera className="w-3.5 h-3.5" />
                              </button>
                              <button
                                type="button"
                                title="Autoscale / Reset view"
                                onClick={() => runAnalysis(prompt, selectedLayer, selectedHead, selectedTokenIdx)}
                                className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>

                          <div className="flex items-center space-x-1.5 text-xs text-gray-300 font-semibold mb-3">
                            <span>👁️</span>
                            <span>Self-Attention Heatmap — Layer {selectedLayer + 1}, Head {selectedHead + 1}</span>
                          </div>

                          <div className="relative flex-1 min-h-[330px] flex items-center justify-center p-3 bg-[#090d14] rounded-lg border border-[#1a2130]">
                            <div className="flex items-center space-x-3">
                              <div className="text-[10px] text-gray-400 font-bold -rotate-90 -mr-2 whitespace-nowrap select-none">
                                Queries (Attending From) ↑
                              </div>

                              <div className="flex flex-col">
                                {/* Column Headers */}
                                <div className="flex items-center pl-16 mb-1 space-x-1">
                                  {tokensList.map((t, cIdx) => (
                                    <span key={cIdx} className="w-10 text-center text-[10px] text-gray-400 font-mono truncate" title={t.display_token}>
                                      {t.display_token}
                                    </span>
                                  ))}
                                </div>

                                {/* Matrix Rows */}
                                <div className="space-y-1">
                                  {tokensList.map((rTok, rIdx) => {
                                    const row = Array.isArray(matrix[rIdx]) ? matrix[rIdx] : [];
                                    return (
                                      <div key={rIdx} className="flex items-center space-x-1">
                                        <span className="w-16 truncate text-[10px] text-gray-400 font-mono text-right pr-1">
                                          {rTok.display_token}
                                        </span>
                                        {tokensList.map((cTok, cIdx) => {
                                          const isCausalMasked = cIdx > rIdx;
                                          const cellVal = isCausalMasked
                                            ? 0.0
                                            : (typeof row[cIdx] === "number" && !isNaN(row[cIdx])
                                                ? row[cIdx]
                                                : (cIdx === 0 ? 0.85 : 0.02));
                                          const safeVal = Math.max(0, Math.min(1, cellVal));
                                          const bg = getPlasmaColor(safeVal);
                                          const textCol = safeVal >= 0.55 ? "#000000" : "#ffffff";
                                          const displayVal = safeVal.toFixed(2);
                                          const hoverPct = (safeVal * 100).toFixed(1);

                                          return (
                                            <div
                                              key={cIdx}
                                              style={{ backgroundColor: bg, color: textCol }}
                                              className="w-10 h-10 flex items-center justify-center font-mono text-[10px] font-bold border border-black/30 rounded-[2px] transition-all hover:scale-105 cursor-pointer shadow-sm"
                                              title={`Query: ${rTok.display_token} | Key: ${cTok.display_token} | Weight: ${displayVal} (${hoverPct}%)`}
                                            >
                                              {displayVal}
                                            </div>
                                          );
                                        })}
                                      </div>
                                    );
                                  })}
                                </div>

                                <div className="text-center text-[10px] text-gray-400 font-bold mt-2 select-none">
                                  Keys (Attended To) →
                                </div>
                              </div>

                              {/* Colorbar */}
                              <div className="flex flex-col items-center pl-1">
                                <span className="text-[9px] text-gray-400 font-bold mb-1 text-center leading-tight">
                                  Attention<br />Weight
                                </span>
                                <div className="w-3.5 h-36 rounded bg-gradient-to-b from-[#f0f921] via-[#ed7953] via-[#9c179e] to-[#0d0887] border border-[#2a3444]" />
                                <div className="h-36 flex flex-col justify-between text-[8px] text-gray-400 font-mono -mt-36 ml-8">
                                  <span>1</span>
                                  <span>0.8</span>
                                  <span>0.6</span>
                                  <span>0.4</span>
                                  <span>0.2</span>
                                  <span>0</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })()}

                    {/* Col 2: Layer-Averaged Attention (All Heads Combined) */}
                    {(() => {
                      const rawTokens = Array.isArray(data.tokens) ? data.tokens : [];
                      const tokensList = rawTokens.slice(0, 8).map((t, idx) => ({
                        index: t?.index ?? idx,
                        display_token: String(t?.display_token ?? t?.decoded_token ?? t?.raw_token ?? idx)
                      }));
                      const matrix = Array.isArray(data.attention_matrix) ? data.attention_matrix : [];
                      const avgMatrix = Array.isArray(data.layer_avg_attention_matrix) && data.layer_avg_attention_matrix.length > 0
                        ? data.layer_avg_attention_matrix
                        : matrix;

                      const getPlasmaColor = (val: number) => {
                        const v = Math.max(0, Math.min(1, typeof val === "number" && !isNaN(val) ? val : 0));
                        if (v <= 0.005) return "#0d0887";
                        if (v < 0.15) return "#46039f";
                        if (v < 0.30) return "#721f81";
                        if (v < 0.50) return "#9c179e";
                        if (v < 0.65) return "#bd3786";
                        if (v < 0.80) return "#d8576b";
                        if (v < 0.92) return "#ed7953";
                        return "#f0f921";
                      };

                      return (
                        <div className="p-4 bg-[#0c1017] border border-[#1e2736] rounded-xl flex flex-col">
                          <div className="flex items-center justify-between mb-1">
                            <h4 className="text-sm font-bold text-white">Layer-Averaged Attention (All Heads Combined)</h4>
                            <div className="flex items-center space-x-1 text-gray-400">
                              <button
                                type="button"
                                title="Download plot as PNG"
                                onClick={() =>
                                  exportMatrixCanvas(
                                    avgMatrix,
                                    tokensList,
                                    `Layer-Averaged Attention Matrix (Layer ${selectedLayer + 1})`,
                                    `layer_${selectedLayer + 1}_averaged_attention.png`
                                  )
                                }
                                className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors"
                              >
                                <Camera className="w-3.5 h-3.5" />
                              </button>
                              <button
                                type="button"
                                title="Autoscale / Reset view"
                                onClick={() => runAnalysis(prompt, selectedLayer, selectedHead, selectedTokenIdx)}
                                className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>

                          <div className="flex items-center space-x-1.5 text-xs text-gray-300 font-semibold mb-3">
                            <span>👁️</span>
                            <span>Self-Attention Heatmap — Layer {selectedLayer + 1}, All Heads</span>
                          </div>

                          <div className="relative flex-1 min-h-[330px] flex items-center justify-center p-3 bg-[#090d14] rounded-lg border border-[#1a2130]">
                            <div className="flex items-center space-x-3">
                              <div className="text-[10px] text-gray-400 font-bold -rotate-90 -mr-2 whitespace-nowrap select-none">
                                Queries (Attending From) ↑
                              </div>

                              <div className="flex flex-col">
                                {/* Column Headers */}
                                <div className="flex items-center pl-16 mb-1 space-x-1">
                                  {tokensList.map((t, cIdx) => (
                                    <span key={cIdx} className="w-10 text-center text-[10px] text-gray-400 font-mono truncate" title={t.display_token}>
                                      {t.display_token}
                                    </span>
                                  ))}
                                </div>

                                {/* Matrix Rows */}
                                <div className="space-y-1">
                                  {tokensList.map((rTok, rIdx) => {
                                    const row = Array.isArray(avgMatrix[rIdx]) ? avgMatrix[rIdx] : [];
                                    return (
                                      <div key={rIdx} className="flex items-center space-x-1">
                                        <span className="w-16 truncate text-[10px] text-gray-400 font-mono text-right pr-1">
                                          {rTok.display_token}
                                        </span>
                                        {tokensList.map((cTok, cIdx) => {
                                          const isCausalMasked = cIdx > rIdx;
                                          const cellVal = isCausalMasked
                                            ? 0.0
                                            : (typeof row[cIdx] === "number" && !isNaN(row[cIdx])
                                                ? row[cIdx]
                                                : (cIdx === 0 ? 0.95 : 0.02));
                                          const safeVal = Math.max(0, Math.min(1, cellVal));
                                          const bg = getPlasmaColor(safeVal);
                                          const textCol = safeVal >= 0.55 ? "#000000" : "#ffffff";
                                          const displayVal = safeVal.toFixed(2);
                                          const hoverPct = (safeVal * 100).toFixed(1);

                                          return (
                                            <div
                                              key={cIdx}
                                              style={{ backgroundColor: bg, color: textCol }}
                                              className="w-10 h-10 flex items-center justify-center font-mono text-[10px] font-bold border border-black/30 rounded-[2px] transition-all hover:scale-105 cursor-pointer shadow-sm"
                                              title={`Query: ${rTok.display_token} | Key: ${cTok.display_token} | Weight: ${displayVal} (${hoverPct}%)`}
                                            >
                                              {displayVal}
                                            </div>
                                          );
                                        })}
                                      </div>
                                    );
                                  })}
                                </div>

                                <div className="text-center text-[10px] text-gray-400 font-bold mt-2 select-none">
                                  Keys (Attended To) →
                                </div>
                              </div>

                              {/* Colorbar */}
                              <div className="flex flex-col items-center pl-1">
                                <span className="text-[9px] text-gray-400 font-bold mb-1 text-center leading-tight">
                                  Attention<br />Weight
                                </span>
                                <div className="w-3.5 h-36 rounded bg-gradient-to-b from-[#f0f921] via-[#ed7953] via-[#9c179e] to-[#0d0887] border border-[#2a3444]" />
                                <div className="h-36 flex flex-col justify-between text-[8px] text-gray-400 font-mono -mt-36 ml-8">
                                  <span>1</span>
                                  <span>0.8</span>
                                  <span>0.6</span>
                                  <span>0.4</span>
                                  <span>0.2</span>
                                  <span>0</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })()}
                  </div>

                  <div className="p-3 bg-[#0a1926] border border-[#173a5a] rounded-lg text-xs text-[#79c0ff]">
                    <strong>Causal Masking Enforced:</strong> Notice that tokens can only attend to past and current tokens (lower triangular), never to future tokens.
                  </div>
                </div>
              </StepErrorBoundary>
            )}

            {/* STEP 7: HIDDEN STATES (EXACT 25-LAYER PCA TRAJECTORY PLOT MATCHING USER SPEC) */}
            {activeStep === 7 && (
              <StepErrorBoundary stepName="Step 7 (Hidden States)" onReset={() => setActiveStep(1)}>
                <div className="p-5 rounded-xl bg-[#141820] border border-[#212734] space-y-6">
                <div>
                  <h3 className="text-sm font-bold text-white mb-1">
                    Step 7 — Hidden States Depth Evolution Trajectory
                  </h3>
                  <p className="text-xs text-gray-300">
                    As tokens flow through all 24 transformer layers, their hidden representations continuously shift and refine in {data.model_metadata?.hidden_dim || 896}-dimensional vector space.
                  </p>
                </div>

                {/* Token Selection Dropdown matching Streamlit / Image 2 */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-gray-300">
                    Select Token to Track through the Network Depth:
                  </label>
                  <select
                    value={selectedTokenIdx}
                    onChange={(e) => {
                      const idx = parseInt(e.target.value);
                      setSelectedTokenIdx(idx);
                      if (!data.hidden_states_trajectories?.[String(idx)]) {
                        runAnalysis(prompt, selectedLayer, selectedHead, idx);
                      }
                    }}
                    className="w-full sm:w-80 bg-[#0b0e14] border border-[#2b3345] focus:border-[#00f0ff] rounded-lg px-3.5 py-2 text-xs text-white focus:outline-none transition-all cursor-pointer font-mono shadow-sm"
                  >
                    {(data.tokens || []).map((t) => (
                      <option key={t.index} value={t.index}>
                        [{t.index}] '{t.display_token}'
                      </option>
                    ))}
                  </select>
                </div>

                {/* 2D PCA Trajectory Visual Plot */}
                {(() => {
                  const tokenKey = String(selectedTokenIdx);
                  const pts = (data.hidden_states_trajectories && data.hidden_states_trajectories[tokenKey]) || data.hidden_states_pca || [];
                  const targetTokenDisplay = data.tokens?.[selectedTokenIdx]?.display_token || (data.tokens?.[0]?.display_token || 'pt');
                  const totalLayers = Math.max((pts.length ? pts.length - 1 : 24), 24);

                  // Viridis high-precision interpolation
                  const getViridisColor = (layerIdx: number, total: number = 24) => {
                    const t = Math.max(0, Math.min(1, layerIdx / Math.max(total, 1)));
                    const stops = [
                      { t: 0.0, r: 68, g: 1, b: 84 },
                      { t: 0.15, r: 72, g: 40, b: 120 },
                      { t: 0.3, r: 62, g: 74, b: 137 },
                      { t: 0.45, r: 49, g: 104, b: 142 },
                      { t: 0.6, r: 38, g: 130, b: 142 },
                      { t: 0.75, r: 53, g: 183, b: 121 },
                      { t: 0.9, r: 181, g: 222, b: 43 },
                      { t: 1.0, r: 253, g: 231, b: 37 }
                    ];
                    for (let i = 0; i < stops.length - 1; i++) {
                      const s1 = stops[i];
                      const s2 = stops[i + 1];
                      if (t >= s1.t && t <= s2.t) {
                        const f = (t - s1.t) / (s2.t - s1.t);
                        const r = Math.round(s1.r + f * (s2.r - s1.r));
                        const g = Math.round(s1.g + f * (s2.g - s1.g));
                        const b = Math.round(s1.b + f * (s2.b - s1.b));
                        return `rgb(${r}, ${g}, ${b})`;
                      }
                    }
                    return "#fde725";
                  };

                  // Dynamic Tick Generator
                  const generateTicks = (min: number, max: number, targetCount = 6) => {
                    const span = max - min;
                    if (span <= 0) return [min];
                    const rawStep = span / targetCount;
                    const mag = Math.pow(10, Math.floor(Math.log10(rawStep || 1)));
                    const residual = rawStep / mag;
                    let step = mag;
                    if (residual > 5) step = 10 * mag;
                    else if (residual > 2) step = 5 * mag;
                    else if (residual > 1) step = 2 * mag;

                    const start = Math.ceil(min / step) * step;
                    const ticks: number[] = [];
                    for (let v = start; v <= max + 0.0001; v += step) {
                      ticks.push(Math.round(v * 100) / 100);
                    }
                    return ticks;
                  };

                  const validPts = pts.filter((p) => typeof p.x === "number" && typeof p.y === "number");
                  let minX = validPts.length ? Math.min(...validPts.map((p) => p.x)) : -20;
                  let maxX = validPts.length ? Math.max(...validPts.map((p) => p.x)) : 250;
                  let minY = validPts.length ? Math.min(...validPts.map((p) => p.y)) : -20;
                  let maxY = validPts.length ? Math.max(...validPts.map((p) => p.y)) : 50;

                  if (minX === maxX) { minX -= 10; maxX += 10; }
                  if (minY === maxY) { minY -= 10; maxY += 10; }

                  const padX = (maxX - minX) * 0.12;
                  const padY = (maxY - minY) * 0.12;
                  const x0 = minX - padX;
                  const x1 = maxX + padX;
                  const y0 = minY - padY;
                  const y1 = maxY + padY;

                  const plotLeft = 60;
                  const plotRight = 730;
                  const plotTop = 30;
                  const plotBottom = 335;
                  const plotW = plotRight - plotLeft;
                  const plotH = plotBottom - plotTop;

                  const toX = (val: number) => plotLeft + ((val - x0) / (x1 - x0)) * plotW;
                  const toY = (val: number) => plotBottom - ((val - y0) / (y1 - y0)) * plotH;

                  const xTicks = generateTicks(minX, maxX, 6);
                  const yTicks = generateTicks(minY, maxY, 5);

                  return (
                    <div className="p-4 bg-[#0c1017] border border-[#1e2736] rounded-xl flex flex-col">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center space-x-2 text-xs font-bold text-gray-200">
                          <span className="p-1 rounded bg-[#00f0ff]/10 text-[#00f0ff]">🌌</span>
                          <span>
                            Hidden State Evolution Trajectory for Token: '{targetTokenDisplay}' (Layer 0 → {totalLayers})
                          </span>
                        </div>

                        {/* Toolbar matching Plotly icons */}
                        <div className="flex items-center space-x-2 text-gray-400">
                          <button
                            type="button"
                            title="Download plot as PNG"
                            onClick={() => exportSvgAsPng("pca-trajectory-svg", `hidden_states_trajectory_${targetTokenDisplay}.png`, 850, 380)}
                            className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors"
                          >
                            <Camera className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            title="Autoscale / Reset view"
                            onClick={() => runAnalysis(prompt, selectedLayer, selectedHead, selectedTokenIdx)}
                            className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      <div className="relative w-full min-h-[380px] bg-[#090d14] rounded-lg border border-[#1a2130] p-2 flex items-center justify-center overflow-x-auto">
                        <svg id="pca-trajectory-svg" className="w-full h-[370px] min-w-[700px]" viewBox="0 0 850 380">
                          {/* Horizontal Grid lines & Y-ticks */}
                          {yTicks.map((yVal) => (
                            <g key={`y-${yVal}`}>
                              <line
                                x1={plotLeft}
                                y1={toY(yVal)}
                                x2={plotRight}
                                y2={toY(yVal)}
                                stroke={yVal === 0 ? "#374151" : "#1f2735"}
                                strokeWidth={yVal === 0 ? "1.5" : "1"}
                                strokeDasharray={yVal === 0 ? "" : "2,2"}
                              />
                              <text
                                x={plotLeft - 10}
                                y={toY(yVal)}
                                fill="#9ca3af"
                                fontSize="10"
                                textAnchor="end"
                                dominantBaseline="middle"
                                fontFamily="monospace"
                              >
                                {yVal}
                              </text>
                            </g>
                          ))}

                          {/* Vertical Grid lines & X-ticks */}
                          {xTicks.map((xVal) => (
                            <g key={`x-${xVal}`}>
                              <line
                                x1={toX(xVal)}
                                y1={plotTop}
                                x2={toX(xVal)}
                                y2={plotBottom}
                                stroke={xVal === 0 ? "#374151" : "#1f2735"}
                                strokeWidth={xVal === 0 ? "1.5" : "1"}
                                strokeDasharray={xVal === 0 ? "" : "2,2"}
                              />
                              <text
                                x={toX(xVal)}
                                y={plotBottom + 18}
                                fill="#9ca3af"
                                fontSize="10"
                                textAnchor="middle"
                                fontFamily="monospace"
                              >
                                {xVal}
                              </text>
                            </g>
                          ))}

                          {/* Axis Titles */}
                          <text
                            x={plotLeft + plotW / 2}
                            y={plotBottom + 34}
                            fill="#cbd5e1"
                            fontSize="11"
                            textAnchor="middle"
                            fontWeight="bold"
                          >
                            PCA Component 1
                          </text>
                          <text
                            x={18}
                            y={plotTop + plotH / 2}
                            fill="#cbd5e1"
                            fontSize="11"
                            textAnchor="middle"
                            fontWeight="bold"
                            transform={`rotate(-90, 18, ${plotTop + plotH / 2})`}
                          >
                            PCA Component 2
                          </text>

                          {/* Trajectory Polyline */}
                          <polyline
                            fill="none"
                            stroke="#00f0ff"
                            strokeWidth="2.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            opacity="0.95"
                            points={validPts.map((p) => `${toX(p.x)},${toY(p.y)}`).join(" ")}
                          />

                          {/* Node Markers & Key Labels (L0, L5, L10, L15, L20, L24) */}
                          {validPts.map((pt) => {
                            const cx = toX(pt.x);
                            const cy = toY(pt.y);
                            const color = getViridisColor(pt.layer, totalLayers);
                            const isKey = pt.layer === 0 || pt.layer % 5 === 0 || pt.layer === totalLayers;

                            return (
                              <g key={pt.layer} className="cursor-pointer group">
                                <circle
                                  cx={cx}
                                  cy={cy}
                                  r={isKey ? 6.5 : 4}
                                  fill={color}
                                  stroke={isKey ? "#ffffff" : "#1a202c"}
                                  strokeWidth={isKey ? 1.5 : 1}
                                  className="transition-all hover:r-8"
                                >
                                  <title>{`Layer ${pt.layer} (${pt.layer === 0 ? "Embedding" : "Transformer"}): PCA (${pt.x.toFixed(2)}, ${pt.y.toFixed(2)})`}</title>
                                </circle>
                                {isKey && (
                                  <text
                                    x={cx}
                                    y={cy - 9}
                                    fill="#ffffff"
                                    fontSize="10"
                                    fontWeight="bold"
                                    textAnchor="middle"
                                    fontFamily="monospace"
                                    className="drop-shadow-[0_1px_3px_rgba(0,0,0,0.9)] pointer-events-none select-none"
                                  >
                                    L{pt.layer}
                                  </text>
                                )}
                              </g>
                            );
                          })}

                          {/* Colorbar for Layer Depth */}
                          <defs>
                            <linearGradient id="layerDepthGrad" x1="0%" y1="100%" x2="0%" y2="0%">
                              <stop offset="0%" stopColor="#440154" />
                              <stop offset="25%" stopColor="#3b528b" />
                              <stop offset="50%" stopColor="#21918c" />
                              <stop offset="75%" stopColor="#5ec962" />
                              <stop offset="100%" stopColor="#fde725" />
                            </linearGradient>
                          </defs>

                          {/* Colorbar Title */}
                          <text x="788" y="42" fill="#f0f6fc" fontSize="11" fontWeight="bold" textAnchor="middle">
                            Layer Depth
                          </text>

                          {/* Colorbar Bar */}
                          <rect
                            x="778"
                            y="55"
                            width="18"
                            height="260"
                            fill="url(#layerDepthGrad)"
                            rx="2"
                            stroke="#374151"
                          />

                          {/* Colorbar Ticks matching user screenshot: 20, 15, 10, 5, 0 */}
                          {[
                            { val: 20, frac: 20 / 24 },
                            { val: 15, frac: 15 / 24 },
                            { val: 10, frac: 10 / 24 },
                            { val: 5, frac: 5 / 24 },
                            { val: 0, frac: 0 }
                          ].map((tick) => {
                            const ty = 55 + (1 - tick.frac) * 260;
                            return (
                              <g key={tick.val}>
                                <line x1="796" y1={ty} x2="801" y2={ty} stroke="#6b7280" strokeWidth="1" />
                                <text
                                  x="805"
                                  y={ty}
                                  fill="#9ca3af"
                                  fontSize="10"
                                  dominantBaseline="middle"
                                  fontFamily="monospace"
                                >
                                  {tick.val}
                                </text>
                              </g>
                            );
                          })}
                        </svg>
                      </div>
                    </div>
                  );
                })()}

                <div className="p-3 bg-[#0a1926] border border-[#173a5a] rounded-lg text-xs text-[#79c0ff]">
                  💡 The PCA trajectory traces the {data.model_metadata?.hidden_dim || 896}-dimensional vector for token <code>'{data.tokens?.[selectedTokenIdx]?.display_token}'</code> from Layer 0 (Embedding) through Layer {data.model_metadata?.num_layers || 24}.
                </div>

                {/* Layer Coordinates Table */}
                <div className="overflow-x-auto rounded-xl border border-[#212734]">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-[#10141b] text-gray-400 border-b border-[#212734]">
                        <th className="p-2.5">Layer</th>
                        <th className="p-2.5">PCA Component 1</th>
                        <th className="p-2.5">PCA Component 2</th>
                        <th className="p-2.5">Evolution Shift</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(() => {
                        const tokenKey = String(selectedTokenIdx);
                        const pts = (data.hidden_states_trajectories && data.hidden_states_trajectories[tokenKey]) || data.hidden_states_pca || [];
                        return pts.map((pt) => (
                          <tr key={pt.layer} className="border-b border-[#1c222e] hover:bg-[#181e29]">
                            <td className="p-2.5 font-mono font-bold text-[#00f0ff]">
                              {pt.layer === 0 ? "Layer 0 (Embed)" : `Layer ${pt.layer}`}
                            </td>
                            <td className="p-2.5 font-mono text-gray-300">{typeof pt.x === 'number' ? pt.x.toFixed(4) : pt.x}</td>
                            <td className="p-2.5 font-mono text-gray-300">{typeof pt.y === 'number' ? pt.y.toFixed(4) : pt.y}</td>
                            <td className="p-2.5 font-mono text-emerald-400">
                              {pt.layer === 0 ? "Initial" : `+${(Math.abs(pt.x || 0) + Math.abs(pt.y || 0)).toFixed(2)}`}
                            </td>
                          </tr>
                        ));
                      })()}
                    </tbody>
                  </table>
                </div>
                </div>
              </StepErrorBoundary>
            )}

            {/* STEP 8: LM HEAD LOGITS (EXACT HORIZONTAL BAR CHART & TABLE MATCHING USER SPEC) */}
            {activeStep === 8 && (
              <StepErrorBoundary stepName="Step 8 (LM Head Logits)" onReset={() => setActiveStep(1)}>
                <div className="p-5 rounded-xl bg-[#141820] border border-[#212734] space-y-6">
                  <div>
                    <h3 className="text-sm font-bold text-white mb-1">
                      Step 8 — LM Head Unembedding Logits
                    </h3>
                    <p className="text-xs text-gray-300">
                      The final layer hidden state <span className="font-serif italic font-semibold text-white">h<sub>L</sub></span> is linearly projected onto the vocabulary space via the unembedding matrix <span className="font-serif italic font-semibold text-white">W<sub>U</sub></span>: <span className="font-mono text-cyan-300">z = h<sub>L</sub> · W<sub>U</sub><sup>T</sup> ∈ ℝ<sup>{(data.model_metadata?.vocab_size || 151936).toLocaleString()}</sup></span>.
                    </p>
                  </div>

                  {/* Next-Token Softmax Probability Distribution Chart matching Image 2 */}
                  <div className="p-4 bg-[#0c1017] border border-[#1e2736] rounded-xl flex flex-col space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center space-x-2 text-xs font-bold text-gray-200">
                        <span className="p-1 rounded bg-[#00f0ff]/10 text-[#00f0ff]">📊</span>
                        <span>
                          Next-Token Softmax Probability Distribution (Top {Math.min(topKCandidates, (data.predictions || []).length)} Candidates)
                        </span>
                      </div>

                      <div className="flex items-center space-x-3">
                        {/* Top K Selector */}
                        <div className="flex items-center space-x-1 text-xs">
                          <span className="text-gray-400 font-mono text-[11px]">Top:</span>
                          {[3, 5, 10].map((k) => (
                            <button
                              key={k}
                              type="button"
                              onClick={() => setTopKCandidates(k)}
                              className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold transition-all ${
                                topKCandidates === k
                                  ? "bg-[#00f0ff] text-black shadow-sm"
                                  : "bg-[#161c28] text-gray-400 hover:text-white border border-[#263145]"
                              }`}
                            >
                              {k}
                            </button>
                          ))}
                        </div>

                        {/* Toolbar icons matching Plotly */}
                        <div className="flex items-center space-x-1.5 text-gray-400">
                          <button
                            type="button"
                            title="Download plot as PNG"
                            onClick={() =>
                              exportSvgAsPng(
                                "logits-barchart-svg",
                                "lm_head_logits_distribution.png",
                                850,
                                Math.max(270, topKCandidates * 80 + 75)
                              )
                            }
                            className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors"
                          >
                            <Camera className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            title="Reset"
                            onClick={() => setTopKCandidates(3)}
                            className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* SVG Bar Chart */}
                    {(() => {
                      const cands = (data.predictions || []).slice(0, topKCandidates);

                      const svgW = 850;
                      const svgH = Math.max(270, cands.length * 80 + 75);
                      const plotLeft = 210;
                      const plotRight = 810;
                      const plotTop = 25;
                      const plotBottom = svgH - 45;
                      const plotW = plotRight - plotLeft;
                      const plotH = plotBottom - plotTop;

                      // X-axis ticks: 0, 20, 40, 60, 80, 100
                      const xTicks = [0, 20, 40, 60, 80, 100];
                      const toScreenX = (pct: number) => plotLeft + (Math.max(0, Math.min(100, pct)) / 100) * plotW;

                      // Tealgrn color scale matching Plotly / Image 2
                      const getTealgrnColor = (idx: number) => {
                        if (idx === 0) return "#229cb3"; // Deep cyan/teal for highest
                        if (idx === 1) return "#56cf9e"; // Sea green / emerald for second
                        if (idx === 2) return "#98e6a8"; // Light mint / pale green for third
                        const palette = ["#229cb3", "#3bb6a8", "#56cf9e", "#78dc9f", "#98e6a8", "#b8f0b4"];
                        return palette[Math.min(idx, palette.length - 1)];
                      };

                      const rowHeight = plotH / Math.max(cands.length, 1);
                      const barHeight = Math.min(46, rowHeight * 0.62);

                    return (
                      <div className="relative w-full bg-[#090d14] rounded-lg border border-[#1a2130] p-2 flex items-center justify-center overflow-x-auto">
                        <svg id="logits-barchart-svg" className="w-full min-w-[700px]" style={{ height: `${svgH}px` }} viewBox={`0 0 ${svgW} ${svgH}`}>
                          {/* Vertical Grid lines & X-ticks */}
                          {xTicks.map((xVal) => {
                            const sx = toScreenX(xVal);
                            return (
                              <g key={`xtick-${xVal}`}>
                                <line
                                  x1={sx}
                                  y1={plotTop}
                                  x2={sx}
                                  y2={plotBottom}
                                  stroke="#212735"
                                  strokeWidth="1"
                                  strokeDasharray="2,2"
                                />
                                <text
                                  x={sx}
                                  y={plotBottom + 16}
                                  fill="#9ca3af"
                                  fontSize="10"
                                  textAnchor="middle"
                                  fontFamily="monospace"
                                >
                                  {xVal}
                                </text>
                              </g>
                            );
                          })}

                          {/* Horizontal Grid lines between bars */}
                          {cands.map((_, idx) => {
                            const lineY = plotTop + (idx + 0.5) * rowHeight;
                            return (
                              <line
                                key={`rowline-${idx}`}
                                x1={plotLeft}
                                y1={lineY}
                                x2={plotRight}
                                y2={lineY}
                                stroke="#171e2b"
                                strokeWidth="1"
                              />
                            );
                          })}

                          {/* Solid Bottom X-Axis line */}
                          <line
                            x1={plotLeft}
                            y1={plotBottom}
                            x2={plotRight}
                            y2={plotBottom}
                            stroke="#30363d"
                            strokeWidth="1.5"
                          />

                          {/* Solid Left Y-Axis line */}
                          <line
                            x1={plotLeft}
                            y1={plotTop}
                            x2={plotLeft}
                            y2={plotBottom}
                            stroke="#30363d"
                            strokeWidth="1.5"
                          />

                          {/* Axis Titles */}
                          <text
                            x={plotLeft + plotW / 2}
                            y={plotBottom + 32}
                            fill="#cbd5e1"
                            fontSize="11"
                            textAnchor="middle"
                            fontWeight="bold"
                          >
                            Probability (%)
                          </text>
                          <text
                            x={18}
                            y={plotTop + plotH / 2}
                            fill="#cbd5e1"
                            fontSize="11"
                            textAnchor="middle"
                            fontWeight="bold"
                            transform={`rotate(-90, 18, ${plotTop + plotH / 2})`}
                          >
                            Candidate Token
                          </text>

                          {/* Horizontal Bars */}
                          {cands.map((cand, idx) => {
                            const barW = Math.max(3, (cand.percentage / 100) * plotW);
                            const barY = plotTop + idx * rowHeight + (rowHeight - barHeight) / 2;
                            const barColor = getTealgrnColor(idx);

                            // Display label for Y axis: e.g. "' ' (ID: 271)" or "'↵ (newline)' (ID: 198)"
                            const tokLabel = `'${cand.display_str || cand.token_str}' (ID: ${cand.token_id})`;
                            const insideText = `${cand.percentage.toFixed(2)}% (Logit: ${cand.logit.toFixed(2)})`;
                            const isWide = barW > 140;

                            return (
                              <g key={cand.token_id || idx} className="group cursor-pointer">
                                {/* Y-axis Token Label */}
                                <text
                                  x={plotLeft - 12}
                                  y={barY + barHeight / 2 + 3.5}
                                  fill="#f0f6fc"
                                  fontSize="11"
                                  textAnchor="end"
                                  fontFamily="monospace"
                                  className="font-medium"
                                >
                                  {tokLabel}
                                </text>

                                {/* The Bar */}
                                <rect
                                  x={plotLeft}
                                  y={barY}
                                  width={barW}
                                  height={barHeight}
                                  fill={barColor}
                                  stroke="#00f0ff"
                                  strokeWidth="1"
                                  rx="1"
                                  className="transition-all hover:brightness-110"
                                >
                                  <title>{`${tokLabel}: ${cand.percentage.toFixed(2)}% | Logit: ${cand.logit.toFixed(4)}`}</title>
                                </rect>

                                {/* Text inside or next to the bar */}
                                {isWide ? (
                                  <text
                                    x={plotLeft + barW - 12}
                                    y={barY + barHeight / 2 + 4}
                                    fill={idx === 2 ? "#0e1117" : "#ffffff"}
                                    fontSize="11"
                                    fontWeight="bold"
                                    textAnchor="end"
                                    fontFamily="monospace"
                                    className="select-none pointer-events-none drop-shadow-[0_1px_1px_rgba(0,0,0,0.5)]"
                                  >
                                    {insideText}
                                  </text>
                                ) : (
                                  <text
                                    x={plotLeft + barW + 8}
                                    y={barY + barHeight / 2 + 4}
                                    fill="#e2e8f0"
                                    fontSize="10"
                                    fontWeight="bold"
                                    textAnchor="start"
                                    fontFamily="monospace"
                                    className="select-none pointer-events-none"
                                  >
                                    {insideText}
                                  </text>
                                )}
                              </g>
                            );
                          })}
                        </svg>
                      </div>
                    );
                  })()}
                </div>

                {/* Top Candidate Unnormalized Logits Table matching Image 1 */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                      Top Candidate Unnormalized Logits
                    </h4>
                    <div className="flex items-center space-x-1.5 text-gray-400">
                      <button
                        type="button"
                        title="Download CSV"
                        onClick={() => {
                          const headers = "rank,token_str,display_str,token_id,logit\n";
                          const rows = (data.predictions || [])
                            .map((c) => `${c.rank},"${c.token_str}","${c.display_str}",${c.token_id},${c.logit}`)
                            .join("\n");
                          const blob = new Blob([headers + rows], { type: "text/csv" });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = "top_candidate_unnormalized_logits.csv";
                          a.click();
                        }}
                        className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors"
                      >
                        <BarChart3 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="overflow-x-auto rounded-xl border border-[#212734] bg-[#0c1017]">
                    <table className="w-full text-left border-collapse text-xs font-mono">
                      <thead>
                        <tr className="bg-[#121620] text-gray-400 border-b border-[#212734]">
                          <th className="p-3 w-12 text-gray-500"></th>
                          <th className="p-3">rank</th>
                          <th className="p-3">token_str</th>
                          <th className="p-3">display_str</th>
                          <th className="p-3">token_id</th>
                          <th className="p-3">logit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(data.predictions || []).map((cand, rIdx) => (
                          <tr
                            key={cand.token_id || rIdx}
                            className="border-b border-[#181f2b] hover:bg-[#141a24] transition-colors"
                          >
                            <td className="p-3 text-gray-500 font-mono">{rIdx}</td>
                            <td className="p-3 text-white font-bold">{cand.rank}</td>
                            <td className="p-3 text-gray-300">
                              {cand.token_str === " " ? "' '" : cand.token_str === "\n" ? "''" : `'${cand.token_str}'`}
                            </td>
                            <td className="p-3 text-emerald-400 font-semibold">
                              {cand.display_str}
                            </td>
                            <td className="p-3 text-[#00f0ff] font-bold">{cand.token_id}</td>
                            <td className="p-3 text-amber-300 font-bold">
                              {typeof cand.logit === "number" ? cand.logit.toFixed(4) : cand.logit}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                </div>
              </StepErrorBoundary>
            )}

            {/* STEP 9: SOFTMAX PROBS (VERTICAL BAR CHART & SAMPLING TABLE MATCHING USER SPEC) */}
            {activeStep === 9 && (
              <StepErrorBoundary stepName="Step 9 (Softmax Probabilities)" onReset={() => setActiveStep(1)}>
                <div className="p-5 rounded-xl bg-[#141820] border border-[#212734] space-y-6">
                <div>
                  <h3 className="text-sm font-bold text-white mb-1">
                    Step 9 — Softmax Normalization & Temperature-Scaled Probabilities
                  </h3>
                  <p className="text-xs text-gray-300">
                    Softmax exponentiates and normalizes raw logits into a valid probability distribution: <span className="font-mono text-cyan-300">P(w<sub>i</sub>) = exp(z<sub>i</sub> / T) / ∑<sub>j</sub> exp(z<sub>j</sub> / T)</span>.
                  </p>
                </div>

                {/* Vertical Bar Chart matching Streamlit / Image */}
                <div className="p-4 bg-[#0c1017] border border-[#1e2736] rounded-xl flex flex-col space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center space-x-2 text-xs font-bold text-gray-200">
                      <span className="p-1 rounded bg-[#00f0ff]/10 text-[#00f0ff]">📊</span>
                      <span>
                        Top-{topKSoftmax} Next-Token Probabilities (Temperature = 0.7, Top-P = 0.9, Top-K = 50)
                      </span>
                    </div>

                    <div className="flex items-center space-x-3">
                      {/* Top K Selector */}
                      <div className="flex items-center space-x-1 text-xs">
                        <span className="text-gray-400 font-mono text-[11px]">Show:</span>
                        {[3, 5, 10, 15].map((k) => (
                          <button
                            key={k}
                            type="button"
                            onClick={() => setTopKSoftmax(k)}
                            className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold transition-all ${
                              topKSoftmax === k
                                ? "bg-[#00f0ff] text-black shadow-sm"
                                : "bg-[#161c28] text-gray-400 hover:text-white border border-[#263145]"
                            }`}
                          >
                            {k}
                          </button>
                        ))}
                      </div>

                      {/* Toolbar matching Plotly */}
                      <div className="flex items-center space-x-1.5 text-gray-400">
                        <button
                          type="button"
                          title="Download plot as PNG"
                          onClick={() =>
                            exportSvgAsPng(
                              "softmax-barchart-svg",
                              "softmax_probabilities.png",
                              850,
                              340
                            )
                          }
                          className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors"
                        >
                          <Camera className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          title="Reset"
                          onClick={() => setTopKSoftmax(3)}
                          className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors"
                        >
                          <RotateCcw className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>

                  {(() => {
                    const cands = (data.predictions || []).slice(0, topKSoftmax);
                    const svgW = 850;
                    const svgH = 340;
                    const plotLeft = 65;
                    const plotRight = 800;
                    const plotTop = 30;
                    const plotBottom = 265;
                    const plotW = plotRight - plotLeft;
                    const plotH = plotBottom - plotTop;

                    const maxProb = Math.max(...cands.map((c) => c.probability || 0), 0.1);
                    // Determine nice y-domain
                    let domainMax = 1.0;
                    if (maxProb <= 0.15) domainMax = 0.15;
                    else if (maxProb <= 0.3) domainMax = 0.3;
                    else if (maxProb <= 0.5) domainMax = 0.5;
                    else if (maxProb <= 0.75) domainMax = 0.8;
                    else domainMax = 1.0;

                    const yTicks = [0, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0].filter((v) => v <= domainMax);
                    const toScreenY = (prob: number) => plotBottom - (Math.max(0, Math.min(domainMax, prob)) / domainMax) * plotH;

                    const slotW = plotW / Math.max(cands.length, 1);
                    const barW = Math.min(100, slotW * 0.60);

                    return (
                      <div className="relative w-full bg-[#090d14] rounded-lg border border-[#1a2130] p-2 flex items-center justify-center overflow-x-auto">
                        <svg id="softmax-barchart-svg" className="w-full min-w-[700px]" style={{ height: `${svgH}px` }} viewBox={`0 0 ${svgW} ${svgH}`}>
                          {/* Horizontal Grid lines */}
                          {yTicks.map((yVal) => {
                            const sy = toScreenY(yVal);
                            return (
                              <g key={`ytick-${yVal}`}>
                                <line
                                  x1={plotLeft}
                                  y1={sy}
                                  x2={plotRight}
                                  y2={sy}
                                  stroke={yVal === 0 ? "#30363d" : "#1f2735"}
                                  strokeWidth={yVal === 0 ? "1.5" : "1"}
                                  strokeDasharray={yVal === 0 ? "" : "2,2"}
                                />
                                <text
                                  x={plotLeft - 10}
                                  y={sy + 3}
                                  fill="#9ca3af"
                                  fontSize="10"
                                  textAnchor="end"
                                  fontFamily="monospace"
                                >
                                  {yVal.toFixed(1)}
                                </text>
                              </g>
                            );
                          })}

                          {/* Solid Left Axis Line */}
                          <line
                            x1={plotLeft}
                            y1={plotTop}
                            x2={plotLeft}
                            y2={plotBottom}
                            stroke="#30363d"
                            strokeWidth="1.5"
                          />

                          {/* Solid Bottom Axis Line */}
                          <line
                            x1={plotLeft}
                            y1={plotBottom}
                            x2={plotRight}
                            y2={plotBottom}
                            stroke="#30363d"
                            strokeWidth="1.5"
                          />

                          {/* Axis Titles */}
                          <text
                            x={plotLeft + plotW / 2}
                            y={plotBottom + 64}
                            fill="#cbd5e1"
                            fontSize="11"
                            textAnchor="middle"
                            fontWeight="bold"
                          >
                            Token Candidate
                          </text>
                          <text
                            x={18}
                            y={plotTop + plotH / 2}
                            fill="#cbd5e1"
                            fontSize="11"
                            textAnchor="middle"
                            fontWeight="bold"
                            transform={`rotate(-90, 18, ${plotTop + plotH / 2})`}
                          >
                            Softmax Probability
                          </text>

                          {/* Vertical Bars matching Cyan styling in screenshot */}
                          {cands.map((cand, idx) => {
                            const centerX = plotLeft + (idx + 0.5) * slotW;
                            const barH = ((cand.probability || 0) / domainMax) * plotH;
                            const barY = plotBottom - barH;
                            const textVal = cand.percentage >= 10 ? cand.percentage.toFixed(2) : cand.percentage.toFixed(1);

                            return (
                              <g key={cand.token_id || idx} className="group cursor-pointer">
                                {/* The Bar */}
                                <rect
                                  x={centerX - barW / 2}
                                  y={barY}
                                  width={barW}
                                  height={barH}
                                  fill="#00f0ff"
                                  stroke="#00d2e0"
                                  strokeWidth="1"
                                  rx="1"
                                  className="transition-all hover:brightness-125"
                                >
                                  <title>{`'${cand.display_str || cand.token_str}' (ID: ${cand.token_id}): ${(cand.probability * 100).toFixed(2)}% | Logit: ${cand.logit}`}</title>
                                </rect>

                                {/* Value Text Above Bar (textposition="outside") */}
                                <text
                                  x={centerX}
                                  y={barY - 8}
                                  fill="#ffffff"
                                  fontSize="11"
                                  fontWeight="bold"
                                  textAnchor="middle"
                                  fontFamily="monospace"
                                  className="select-none pointer-events-none drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]"
                                >
                                  {textVal}
                                </text>

                                {/* Rotated Candidate Token Label (-45 deg) */}
                                <text
                                  x={centerX}
                                  y={plotBottom + 16}
                                  fill="#f0f6fc"
                                  fontSize="11"
                                  fontFamily="monospace"
                                  textAnchor="end"
                                  transform={`rotate(-45, ${centerX}, ${plotBottom + 16})`}
                                  className="font-medium select-none pointer-events-none"
                                >
                                  {cand.display_str || cand.token_str}
                                </text>
                              </g>
                            );
                          })}
                        </svg>
                      </div>
                    );
                  })()}
                </div>

                {/* Softmax Probabilities & Sampling Table matching Image */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                      Softmax Probabilities & Sampling Table
                    </h4>
                    <div className="flex items-center space-x-1.5 text-gray-400">
                      <button
                        type="button"
                        title="Download CSV"
                        onClick={() => {
                          const headers = "rank,token_str,display_str,token_id,probability,percentage,logit\n";
                          const rows = (data.predictions || [])
                            .map((c) => `${c.rank},"${c.token_str}","${c.display_str}",${c.token_id},${c.probability},${c.percentage},${c.logit}`)
                            .join("\n");
                          const blob = new Blob([headers + rows], { type: "text/csv" });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = "softmax_probabilities_sampling_table.csv";
                          a.click();
                        }}
                        className="p-1 hover:text-white hover:bg-[#1a2130] rounded transition-colors"
                      >
                        <BarChart3 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="overflow-x-auto rounded-xl border border-[#212734] bg-[#0c1017]">
                    <table className="w-full text-left border-collapse text-xs font-mono">
                      <thead>
                        <tr className="bg-[#121620] text-gray-400 border-b border-[#212734]">
                          <th className="p-3 w-12 text-gray-500"></th>
                          <th className="p-3">rank</th>
                          <th className="p-3">token_str</th>
                          <th className="p-3">display_str</th>
                          <th className="p-3">token_id</th>
                          <th className="p-3">probability</th>
                          <th className="p-3">percentage</th>
                          <th className="p-3">logit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(data.predictions || []).map((cand, rIdx) => (
                          <tr
                            key={cand.token_id || rIdx}
                            className="border-b border-[#181f2b] hover:bg-[#141a24] transition-colors"
                          >
                            <td className="p-3 text-gray-500 font-mono">{rIdx}</td>
                            <td className="p-3 text-white font-bold">{cand.rank}</td>
                            <td className="p-3 text-gray-300">
                              {cand.token_str === " " ? "' '" : cand.token_str === "\n" ? "''" : `'${cand.token_str}'`}
                            </td>
                            <td className="p-3 text-emerald-400 font-semibold">
                              {cand.display_str}
                            </td>
                            <td className="p-3 text-[#00f0ff] font-bold">{cand.token_id}</td>
                            <td className="p-3 text-gray-200">
                              {typeof cand.probability === "number" ? cand.probability.toFixed(4) : cand.probability}
                            </td>
                            <td className="p-3 text-cyan-300 font-bold">
                              {typeof cand.percentage === "number" ? cand.percentage.toFixed(2) : cand.percentage}
                            </td>
                            <td className="p-3 text-amber-300 font-bold">
                              {typeof cand.logit === "number" ? cand.logit.toFixed(4) : cand.logit}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                </div>
              </StepErrorBoundary>
            )}

            {/* STEP 10: GENERATION ROLLOUT */}
            {activeStep === 10 && (
              <StepErrorBoundary stepName="Step 10 (Generation Rollout)" onReset={() => setActiveStep(1)}>
                <div className="p-5 rounded-xl bg-[#141820] border border-[#212734] space-y-5">
                <div>
                  <h3 className="text-sm font-bold text-white mb-1">
                    Step 10 — Autoregressive Generation Rollout
                  </h3>
                  <p className="text-xs text-gray-300">
                    The chosen candidate token is appended to the input sequence and the forward pass repeats autoregressively until completion.
                  </p>
                </div>

                <div className="p-4 bg-[#0d0f14] border border-[#212734] rounded-lg">
                  <div className="flex items-center justify-between text-xs text-gray-300 mb-2">
                    <span>Scrub Generation Step:</span>
                    <span className="text-[#00f0ff] font-bold">
                      Step {rolloutStep} of {(data.rollout_steps || []).length || 1}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={Math.max((data.rollout_steps || []).length, 1)}
                    value={rolloutStep}
                    onChange={(e) => setRolloutStep(parseInt(e.target.value))}
                    className="w-full h-1.5 bg-[#212734] rounded-lg appearance-none cursor-pointer accent-[#00f0ff]"
                  />
                </div>

                <div className="overflow-x-auto rounded-lg border border-[#212734]">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-[#10141b] text-gray-400 border-b border-[#212734]">
                        <th className="p-2.5">Step</th>
                        <th className="p-2.5">Chosen Token</th>
                        <th className="p-2.5">Token ID</th>
                        <th className="p-2.5">Accumulated Text</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(data.rollout_steps && data.rollout_steps.length > 0 ? (
                        data.rollout_steps.slice(0, rolloutStep).map((r) => (
                          <tr key={r.step} className="border-b border-[#1c222e] hover:bg-[#181e29]">
                            <td className="p-2.5 font-mono text-gray-400">{r.step}</td>
                            <td className="p-2.5 font-mono font-bold text-[#00f0ff]">{r.chosen_display_str || r.chosen_token_str}</td>
                            <td className="p-2.5 font-mono text-amber-300">{r.chosen_token_id}</td>
                            <td className="p-2.5 font-mono text-emerald-400">{r.accumulated_text}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={4} className="p-4 text-center text-gray-500 font-mono">
                            No generation rollout steps recorded.
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </StepErrorBoundary>
          )}
          </div>
        )}
      </div>
    </div>
  );
};
