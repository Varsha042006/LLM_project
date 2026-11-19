"use client";

import React, { useState, useEffect } from "react";
import { X, Settings as SettingsIcon, Key, Server, Sliders, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { UserSettings, getSettings, updateSettings } from "../lib/api";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSettingsUpdated?: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  onSettingsUpdated,
}) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [provider, setProvider] = useState("groq");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [modelName, setModelName] = useState("openai/gpt-oss-120b");
  const [temperature, setTemperature] = useState(0.7);
  const [topP, setTopP] = useState(0.9);
  const [systemPrompt, setSystemPrompt] = useState("You are a helpful, brilliant, and friendly AI assistant.");

  useEffect(() => {
    if (isOpen) {
      loadCurrentSettings();
    }
  }, [isOpen]);

  const loadCurrentSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSettings();
      setProvider(data.provider || "groq");
      setBaseUrl(data.base_url || "");
      setModelName(data.model_name || "openai/gpt-oss-120b");
      setTemperature(data.temperature ?? 0.7);
      setTopP(data.top_p ?? 0.9);
      setSystemPrompt(data.system_prompt || "You are a helpful, brilliant, and friendly AI assistant.");
    } catch (err: any) {
      setError("Failed to load settings.");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await updateSettings({
        provider,
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
        model_name: modelName,
        temperature,
        top_p: topP,
        system_prompt: systemPrompt,
      });
      setSuccess("Settings updated successfully!");
      if (onSettingsUpdated) onSettingsUpdated();
      setTimeout(() => {
        setSuccess(null);
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err.message || "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 dark:bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-md bg-white dark:bg-[#1a1a1a] border border-gray-200 dark:border-[#333333] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-[#2b2b2b]">
          <div className="flex items-center space-x-2">
            <SettingsIcon className="w-5 h-5 text-[#10a37f]" />
            <h3 className="font-bold text-gray-900 dark:text-gray-100 text-sm">Hosted Inference & Model Settings</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-[#262626] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Content */}
        <form onSubmit={handleSave} className="p-5 overflow-y-auto space-y-4">
          {error && (
            <div className="flex items-center space-x-2 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700/50 rounded-xl text-xs text-red-700 dark:text-red-200">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-500" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="flex items-center space-x-2 p-3 bg-emerald-50 dark:bg-[#10a37f]/10 border border-emerald-200 dark:border-[#10a37f]/40 rounded-xl text-xs text-emerald-700 dark:text-[#10a37f]">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-[#10a37f]" />
              <span>{success}</span>
            </div>
          )}

          {loading ? (
            <div className="py-12 flex justify-center items-center">
              <Loader2 className="w-6 h-6 text-[#10a37f] animate-spin" />
            </div>
          ) : (
            <>
              {/* Provider Selection */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5">
                  Hosted Inference Provider
                </label>
                <select
                  value={provider}
                  onChange={(e) => {
                    const p = e.target.value;
                    setProvider(p);
                    if (p === "groq") {
                      setModelName("openai/gpt-oss-120b");
                      setBaseUrl("https://api.groq.com/openai/v1");
                    } else if (p === "huggingface") {
                      setModelName("meta-llama/Llama-3.2-3B-Instruct");
                      setBaseUrl("https://api-inference.huggingface.co/v1");
                    } else if (p === "gemini") {
                      setModelName("gemini-3.5-flash");
                      setBaseUrl("https://generativelanguage.googleapis.com/v1beta/openai/");
                    } else if (p === "openrouter") {
                      setModelName("meta-llama/llama-3.3-70b-instruct");
                      setBaseUrl("https://openrouter.ai/api/v1");
                    }
                  }}
                  className="w-full bg-gray-50 dark:bg-[#141414] border border-gray-200 dark:border-[#333333] focus:border-[#10a37f] rounded-xl px-3 py-2 text-xs text-gray-900 dark:text-gray-100 focus:outline-none"
                >
                  <option value="groq">Groq Cloud (GPT-OSS 120B • Ultra Fast)</option>
                  <option value="huggingface">HuggingFace Inference API</option>
                  <option value="openrouter">OpenRouter (Multi-Provider)</option>
                  <option value="gemini">Google Gemini API</option>
                  <option value="custom">Custom OpenAI-Compatible Endpoint</option>
                </select>
              </div>

              {/* API Key */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                    API Key (Hosted Provider)
                  </label>
                  <span className="text-[10px] text-gray-400">Optional for demo simulation</span>
                </div>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="gsk_... or hf_... or AIza..."
                  className="w-full bg-gray-50 dark:bg-[#141414] border border-gray-200 dark:border-[#333333] focus:border-[#10a37f] rounded-xl px-3 py-2 text-xs text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none"
                />
              </div>

              {/* Base URL */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Endpoint Base URL
                </label>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://api.groq.com/openai/v1"
                  className="w-full bg-gray-50 dark:bg-[#141414] border border-gray-200 dark:border-[#333333] focus:border-[#10a37f] rounded-xl px-3 py-2 text-xs text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none"
                />
              </div>

              {/* Model Name */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Model Identifier
                </label>
                <input
                  type="text"
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                  placeholder="openai/gpt-oss-120b"
                  className="w-full bg-gray-50 dark:bg-[#141414] border border-gray-200 dark:border-[#333333] focus:border-[#10a37f] rounded-xl px-3 py-2 text-xs text-gray-900 dark:text-gray-100 focus:outline-none font-mono"
                />
              </div>

              {/* Hyperparameters: Temperature & Top-P */}
              <div className="grid grid-cols-2 gap-3 pt-1">
                <div>
                  <div className="flex justify-between text-xs text-gray-700 dark:text-gray-300 mb-1">
                    <span>Temperature</span>
                    <span className="font-mono text-gray-500 dark:text-gray-400">{temperature.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1.5"
                    step="0.05"
                    value={temperature}
                    onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    className="w-full accent-[#10a37f]"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-xs text-gray-700 dark:text-gray-300 mb-1">
                    <span>Top-P</span>
                    <span className="font-mono text-gray-500 dark:text-gray-400">{topP.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    value={topP}
                    onChange={(e) => setTopP(parseFloat(e.target.value))}
                    className="w-full accent-[#10a37f]"
                  />
                </div>
              </div>

              {/* System Prompt */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  System Instructions
                </label>
                <textarea
                  rows={2}
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  className="w-full bg-gray-50 dark:bg-[#141414] border border-gray-200 dark:border-[#333333] focus:border-[#10a37f] rounded-xl px-3 py-2 text-xs text-gray-900 dark:text-gray-100 focus:outline-none resize-none"
                />
              </div>

              {/* HuggingFace Token Info */}
              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700/40 rounded-xl">
                <div className="flex items-center space-x-1.5 mb-1">
                  <span className="text-blue-700 dark:text-blue-400 text-xs font-semibold">🖼️ AI Image Editing</span>
                  <span className="text-[10px] text-blue-700 bg-blue-100 dark:text-blue-500 dark:bg-blue-900/40 px-1.5 py-0.5 rounded-full font-medium">HuggingFace</span>
                </div>
                <p className="text-[11px] text-blue-900/80 dark:text-blue-200/80 leading-relaxed">
                  For AI-powered image inpainting and editing (adding/removing objects, modifying regions), set your free HuggingFace token as an environment variable:
                </p>
                <code className="block mt-1.5 text-[11px] font-mono text-emerald-800 dark:text-green-300 bg-white dark:bg-[#0a0a0a] border border-blue-200 dark:border-[#2a2a2a] rounded-lg px-2 py-1 select-all">
                  HF_API_TOKEN=hf_your_token_here
                </code>
                <a
                  href="https://huggingface.co/settings/tokens"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block mt-1.5 text-[10px] text-blue-600 dark:text-blue-400 hover:underline underline-offset-2"
                >
                  Get a free token at huggingface.co/settings/tokens →
                </a>
              </div>
            </>
          )}

          {/* Submit */}
          <div className="pt-2 flex justify-end space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 dark:bg-[#222222] dark:hover:bg-[#2b2b2b] text-xs font-semibold text-gray-700 dark:text-gray-300 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 rounded-xl bg-[#10a37f] hover:bg-[#0e8c6d] text-xs font-semibold text-white transition-all shadow-md flex items-center space-x-1.5"
            >
              {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Save Configuration</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
