"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  X,
  Paintbrush,
  Eraser,
  Undo2,
  Redo2,
  Trash2,
  Sparkles,
  Download,
  Eye,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Layers,
  ArrowRight,
  Maximize2
} from "lucide-react";
import { editImage, getImageLineage, ImageVersionItem, ImageEditResult } from "../lib/api";

interface ImageEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  imageUrl: string;
  chatId?: string | null;
  onApplyEditToChat?: (resultImageUrl: string, instruction: string) => void;
}

export const ImageEditorModal: React.FC<ImageEditorModalProps> = ({
  isOpen,
  onClose,
  imageUrl,
  chatId,
  onApplyEditToChat,
}) => {
  const [currentUrl, setCurrentUrl] = useState<string>(imageUrl);
  const [originalUrl, setOriginalUrl] = useState<string>(imageUrl);
  const [instruction, setInstruction] = useState<string>("");
  const [tool, setTool] = useState<"brush" | "eraser">("brush");
  const [brushSize, setBrushSize] = useState<number>(32);
  const [isDrawing, setIsDrawing] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [compareMode, setCompareMode] = useState<boolean>(false);
  const [versions, setVersions] = useState<ImageVersionItem[]>([]);
  const [hasDrawnMask, setHasDrawnMask] = useState<boolean>(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const historyStackRef = useRef<ImageData[]>([]);
  const historyIndexRef = useRef<number>(-1);

  // Initialize modal state on open
  useEffect(() => {
    if (isOpen) {
      setCurrentUrl(imageUrl);
      setOriginalUrl(imageUrl);
      setInstruction("");
      setErrorMsg(null);
      setSuccessMsg(null);
      setCompareMode(false);
      setHasDrawnMask(false);
      loadLineage();
    }
  }, [isOpen, imageUrl]);

  const loadLineage = async () => {
    if (chatId) {
      try {
        const vList = await getImageLineage(chatId);
        setVersions(vList);
      } catch (err) {
        console.error("Failed to load lineage:", err);
      }
    }
  };

  // Sync canvas size with rendered image size
  const syncCanvasDimensions = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imageRef.current;
    if (!canvas || !img) return;

    const rect = img.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      canvas.width = rect.width;
      canvas.height = rect.height;
      clearCanvas();
    }
  }, []);

  useEffect(() => {
    window.addEventListener("resize", syncCanvasDimensions);
    return () => window.removeEventListener("resize", syncCanvasDimensions);
  }, [syncCanvasDimensions]);

  const saveHistoryState = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const currentData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    // Trim any future states after current index
    const newStack = historyStackRef.current.slice(0, historyIndexRef.current + 1);
    newStack.push(currentData);
    if (newStack.length > 20) newStack.shift(); // limit history depth
    historyStackRef.current = newStack;
    historyIndexRef.current = newStack.length - 1;
    setHasDrawnMask(true);
  };

  const handleUndo = () => {
    if (historyIndexRef.current > 0) {
      historyIndexRef.current -= 1;
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (canvas && ctx) {
        ctx.putImageData(historyStackRef.current[historyIndexRef.current], 0, 0);
      }
    } else if (historyIndexRef.current === 0) {
      clearCanvas();
      historyIndexRef.current = -1;
      historyStackRef.current = [];
      setHasDrawnMask(false);
    }
  };

  const handleRedo = () => {
    if (historyIndexRef.current < historyStackRef.current.length - 1) {
      historyIndexRef.current += 1;
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (canvas && ctx) {
        ctx.putImageData(historyStackRef.current[historyIndexRef.current], 0, 0);
      }
    }
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasDrawnMask(false);
  };

  const invertMask = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imgData.data;
    for (let i = 0; i < data.length; i += 4) {
      // Invert painted alpha: if painted (alpha > 50), make 0; if unpainted, fill with emerald mask
      if (data[i + 3] > 30) {
        data[i + 3] = 0;
      } else {
        data[i] = 16;      // R: emerald
        data[i + 1] = 185;  // G
        data[i + 2] = 129;  // B
        data[i + 3] = 170;  // Alpha
      }
    }
    ctx.putImageData(imgData, 0, 0);
    saveHistoryState();
  };

  const autoSelectSubject = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    clearCanvas();
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const rx = canvas.width * 0.3;
    const ry = canvas.height * 0.35;

    ctx.fillStyle = "rgba(16, 185, 129, 0.65)";
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    ctx.fill();
    saveHistoryState();
  };

  const autoSelectBackground = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    clearCanvas();
    // Fill all, then cut out center
    ctx.fillStyle = "rgba(16, 185, 129, 0.65)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.globalCompositeOperation = "destination-out";
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const rx = canvas.width * 0.28;
    const ry = canvas.height * 0.33;
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalCompositeOperation = "source-over";

    saveHistoryState();
  };

  // Drawing event handlers
  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDrawing(true);
    draw(e);
  };

  const stopDrawing = () => {
    if (isDrawing) {
      setIsDrawing(false);
      saveHistoryState();
    }
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing && e.type !== "mousedown") return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    ctx.lineWidth = brushSize;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    if (tool === "eraser") {
      ctx.globalCompositeOperation = "destination-out";
      ctx.strokeStyle = "rgba(0,0,0,1)";
    } else {
      ctx.globalCompositeOperation = "source-over";
      ctx.strokeStyle = "rgba(16, 185, 129, 0.65)"; // Glowing emerald mask overlay
    }

    ctx.beginPath();
    ctx.arc(x, y, brushSize / 2, 0, Math.PI * 2);
    ctx.fillStyle = ctx.strokeStyle;
    ctx.fill();
  };

  // Generate binary PNG mask for server
  const exportBinaryMask = (): string | undefined => {
    const canvas = canvasRef.current;
    if (!canvas || !hasDrawnMask) return undefined;

    // Create an offscreen canvas with white for painted area and black for unpainted
    const off = document.createElement("canvas");
    off.width = canvas.width;
    off.height = canvas.height;
    const offCtx = off.getContext("2d");
    if (!offCtx) return undefined;

    // Fill background black (keep original)
    offCtx.fillStyle = "#000000";
    offCtx.fillRect(0, 0, off.width, off.height);

    // Get alpha from user canvas
    const userCtx = canvas.getContext("2d");
    if (!userCtx) return undefined;
    const userImgData = userCtx.getImageData(0, 0, canvas.width, canvas.height);
    const offImgData = offCtx.getImageData(0, 0, off.width, off.height);

    for (let i = 0; i < userImgData.data.length; i += 4) {
      const alpha = userImgData.data[i + 3];
      if (alpha > 20) {
        // Painted area -> 255 White (editable region)
        offImgData.data[i] = 255;
        offImgData.data[i + 1] = 255;
        offImgData.data[i + 2] = 255;
        offImgData.data[i + 3] = 255;
      }
    }
    offCtx.putImageData(offImgData, 0, 0);
    return off.toDataURL("image/png");
  };

  // Execute Edit
  const handleApplyEdit = async () => {
    if (!instruction.trim()) {
      setErrorMsg("Please provide an editing instruction (e.g. 'add sunglasses', 'remove watch').");
      return;
    }

    setIsProcessing(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const maskData = exportBinaryMask();
      const res = await editImage({
        image_url: currentUrl,
        instruction: instruction.trim(),
        mask_data: maskData,
        chat_id: chatId || undefined,
      });

      setCurrentUrl(res.image_url);
      setSuccessMsg(`Edit applied successfully! (${res.operation.replace("_", " ")})`);
      clearCanvas();
      await loadLineage();

      if (onApplyEditToChat) {
        onApplyEditToChat(res.image_url, instruction.trim());
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to apply image edit. Check network or server status.");
    } finally {
      setIsProcessing(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-5xl h-[92vh] bg-[#141822] border border-[#2a3449] rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Top Header */}
        <div className="px-5 py-3.5 bg-[#10141d] border-b border-[#242d3f] flex items-center justify-between flex-shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-[#10a37f]/20 border border-[#10a37f]/40 flex items-center justify-center text-[#10a37f]">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-gray-100 flex items-center space-x-2">
                <span>Universal AI Image Editor & Inpainting</span>
                {versions.length > 0 && (
                  <span className="px-2 py-0.5 text-[10px] font-semibold bg-[#1a2333] border border-[#2b3952] text-[#00f0ff] rounded-full">
                    v{versions.length}
                  </span>
                )}
              </h3>
              <p className="text-[11px] text-gray-400">
                Paint over the region to edit, or apply full-image transformations. Unselected pixels are 100% preserved.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {/* Version Switcher */}
            {versions.length > 1 && (
              <div className="flex items-center space-x-1 mr-2 bg-[#171e2c] p-1 rounded-lg border border-[#253247]">
                <Layers className="w-3.5 h-3.5 text-gray-400 ml-1" />
                {versions.map((v) => (
                  <button
                    key={v.version}
                    onClick={() => setCurrentUrl(v.image_url)}
                    className={`px-2 py-0.5 text-[11px] font-bold rounded-md transition-colors ${
                      currentUrl === v.image_url
                        ? "bg-[#10a37f] text-white"
                        : "text-gray-400 hover:text-white hover:bg-[#202b3d]"
                    }`}
                  >
                    v{v.version}
                  </button>
                ))}
              </div>
            )}

            {/* Compare with Original Button */}
            <button
              type="button"
              onMouseDown={() => setCompareMode(true)}
              onMouseUp={() => setCompareMode(false)}
              onTouchStart={() => setCompareMode(true)}
              onTouchEnd={() => setCompareMode(false)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors border ${
                compareMode
                  ? "bg-[#00f0ff]/20 text-[#00f0ff] border-[#00f0ff]/50"
                  : "bg-[#1e2535] text-gray-300 border-[#2f3b52] hover:text-white"
              }`}
              title="Hold to preview original image"
            >
              <Eye className="w-3.5 h-3.5" />
              <span>{compareMode ? "Viewing Original" : "Hold to Compare"}</span>
            </button>

            {/* Download Button */}
            <a
              href={currentUrl}
              download="ai_edited_image.jpg"
              className="p-2 rounded-lg bg-[#1e2535] hover:bg-[#273247] text-gray-300 hover:text-white transition-colors border border-[#2f3b52]"
              title="Download image"
            >
              <Download className="w-4 h-4" />
            </a>

            {/* Close Button */}
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-[#222b3d] transition-colors ml-1"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Workspace Center (Canvas & Image Area) */}
        <div className="flex-1 relative flex items-center justify-center p-4 bg-[#0a0d14] overflow-hidden select-none">
          <div className="relative max-w-full max-h-full rounded-xl overflow-hidden shadow-2xl border border-[#1e2738] flex items-center justify-center">
            {/* The Image */}
            <img
              ref={imageRef}
              src={compareMode ? originalUrl : currentUrl}
              alt="Editor Subject"
              onLoad={syncCanvasDimensions}
              className="max-h-[60vh] max-w-full object-contain pointer-events-none"
            />

            {/* Canvas Mask Layer (Active unless in compare mode) */}
            {!compareMode && (
              <canvas
                ref={canvasRef}
                onMouseDown={startDrawing}
                onMouseUp={stopDrawing}
                onMouseMove={draw}
                onMouseLeave={stopDrawing}
                className={`absolute inset-0 cursor-crosshair ${
                  isProcessing ? "pointer-events-none opacity-50" : ""
                }`}
              />
            )}

            {/* Processing Spinner Overlay */}
            {isProcessing && (
              <div className="absolute inset-0 bg-black/75 flex flex-col items-center justify-center space-y-3 z-30">
                <Loader2 className="w-10 h-10 text-[#00f0ff] animate-spin" />
                <p className="text-sm font-semibold text-gray-200">
                  Executing Universal Inpainting & Pixel Compositing...
                </p>
                <p className="text-xs text-gray-400">
                  Preserving untouched pixels and matching original dimensions
                </p>
              </div>
            )}
          </div>

          {/* Floating Tool Palette Overlay */}
          {!compareMode && (
            <div className="absolute top-6 left-6 bg-[#161d2b]/95 border border-[#2b374d] rounded-2xl p-2 shadow-2xl flex flex-col space-y-2 backdrop-blur-md z-20">
              <div className="flex items-center space-x-1 border-b border-[#253147] pb-2">
                <button
                  type="button"
                  onClick={() => setTool("brush")}
                  className={`p-2 rounded-xl transition-all ${
                    tool === "brush"
                      ? "bg-[#10a37f] text-white shadow-md shadow-[#10a37f]/30"
                      : "text-gray-400 hover:text-white hover:bg-[#202a3d]"
                  }`}
                  title="Inpainting Brush (Paint area to change)"
                >
                  <Paintbrush className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setTool("eraser")}
                  className={`p-2 rounded-xl transition-all ${
                    tool === "eraser"
                      ? "bg-[#10a37f] text-white shadow-md shadow-[#10a37f]/30"
                      : "text-gray-400 hover:text-white hover:bg-[#202a3d]"
                  }`}
                  title="Eraser (Remove mask)"
                >
                  <Eraser className="w-4 h-4" />
                </button>
              </div>

              {/* Brush Size Slider */}
              <div className="flex flex-col items-center py-1">
                <span className="text-[10px] font-semibold text-gray-400 mb-1">{brushSize}px</span>
                <input
                  type="range"
                  min={8}
                  max={80}
                  value={brushSize}
                  onChange={(e) => setBrushSize(Number(e.target.value))}
                  className="w-20 accent-[#10a37f] cursor-pointer h-1.5 bg-[#253147] rounded-lg"
                />
              </div>

              {/* Undo / Redo / Clear */}
              <div className="flex items-center space-x-1 border-t border-[#253147] pt-2">
                <button
                  type="button"
                  onClick={handleUndo}
                  className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-[#202a3d] transition-colors"
                  title="Undo stroke"
                >
                  <Undo2 className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={handleRedo}
                  className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-[#202a3d] transition-colors"
                  title="Redo stroke"
                >
                  <Redo2 className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={clearCanvas}
                  className="p-1.5 rounded-lg text-gray-400 hover:text-red-400 hover:bg-[#202a3d] transition-colors"
                  title="Clear mask"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* Quick Auto-Selection Helpers */}
          {!compareMode && (
            <div className="absolute top-6 right-6 flex items-center space-x-2 bg-[#161d2b]/95 border border-[#2b374d] rounded-2xl p-1.5 shadow-2xl backdrop-blur-md z-20">
              <button
                type="button"
                onClick={autoSelectSubject}
                className="px-2.5 py-1 text-[11px] font-semibold text-gray-300 hover:text-[#00f0ff] hover:bg-[#202b3e] rounded-xl transition-all"
              >
                🎯 Select Subject
              </button>
              <button
                type="button"
                onClick={autoSelectBackground}
                className="px-2.5 py-1 text-[11px] font-semibold text-gray-300 hover:text-[#00f0ff] hover:bg-[#202b3e] rounded-xl transition-all"
              >
                🏞️ Select Background
              </button>
              <button
                type="button"
                onClick={invertMask}
                className="px-2.5 py-1 text-[11px] font-semibold text-gray-300 hover:text-[#00f0ff] hover:bg-[#202b3e] rounded-xl transition-all"
              >
                🔄 Invert Mask
              </button>
            </div>
          )}
        </div>

        {/* Bottom Control Bar */}
        <div className="p-4 bg-[#10141e] border-t border-[#242d3f] flex flex-col space-y-3 flex-shrink-0">
          {/* Quick Preset Buttons */}
          <div className="flex items-center space-x-2 overflow-x-auto pb-1 text-xs">
            <span className="text-[11px] text-gray-400 font-semibold flex-shrink-0">⚡ Quick Actions:</span>
            {[
              { label: "🕶️ Add Sunglasses", text: "add stylish black sunglasses" },
              { label: "🎩 Add Top Hat", text: "add a stylish vintage hat" },
              { label: "🗑️ Remove Object", text: "remove the selected object seamlessly" },
              { label: "🏔️ Snowy Mountains", text: "change background to snowy mountain peaks" },
              { label: "🌇 Golden Hour", text: "make lighting warm golden hour sunset" },
              { label: "🎨 Anime Style", text: "transform image into high quality anime style" },
              { label: "🔲 Black & White", text: "turn this into high contrast black and white" },
              { label: "🌙 Night Mode", text: "make this image nighttime with atmospheric lighting" },
            ].map((p, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setInstruction(p.text)}
                className="px-2.5 py-1 rounded-full bg-[#18202d] hover:bg-[#232e42] text-gray-300 hover:text-[#00f0ff] border border-[#273449] transition-all flex-shrink-0 text-[11px] font-medium"
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Main Instruction Input & Action Button */}
          <div className="flex items-center space-x-3">
            <div className="flex-1 relative">
              <input
                type="text"
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !isProcessing) handleApplyEdit();
                }}
                disabled={isProcessing}
                placeholder={
                  hasDrawnMask
                    ? "Describe what to add, remove, or replace in the selected region (e.g. 'add black sunglasses')..."
                    : "Describe modification or choose a quick action (e.g. 'change background to a beach')..."
                }
                className="w-full bg-[#1b2230] border border-[#303c54] focus:border-[#00f0ff]/60 rounded-xl px-4 py-2.5 text-sm text-gray-100 placeholder-gray-400 focus:outline-none transition-colors shadow-inner"
              />
              {hasDrawnMask && (
                <span className="absolute right-3 top-2.5 px-2 py-0.5 rounded-md bg-[#10a37f]/20 border border-[#10a37f]/40 text-[#10a37f] text-[10px] font-bold">
                  Mask Active
                </span>
              )}
            </div>

            <button
              type="button"
              onClick={handleApplyEdit}
              disabled={isProcessing || !instruction.trim()}
              className={`px-5 py-2.5 rounded-xl font-bold text-sm flex items-center space-x-2 transition-all shadow-lg ${
                isProcessing || !instruction.trim()
                  ? "bg-[#252f42] text-gray-500 cursor-not-allowed"
                  : "bg-[#10a37f] hover:bg-[#0e8f6e] text-white shadow-[#10a37f]/25"
              }`}
            >
              {isProcessing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Apply AI Edit</span>
                </>
              )}
            </button>
          </div>

          {/* Feedback & Status Messages */}
          {errorMsg && (
            <div className="p-2.5 rounded-lg bg-red-950/60 border border-red-800/80 flex items-center space-x-2 text-red-200 text-xs animate-in fade-in">
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}
          {successMsg && (
            <div className="p-2 rounded-lg bg-emerald-950/60 border border-emerald-800/80 flex items-center space-x-2 text-emerald-200 text-xs animate-in fade-in">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

