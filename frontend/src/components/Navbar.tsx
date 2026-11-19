"use client";

import React, { useState } from "react";
import { ChevronDown, Sparkles, Moon, Sun, Plus, Radio, Sliders } from "lucide-react";
import { User, HostedModel } from "../lib/api";

interface NavbarProps {
  user?: User | null;
  selectedModel: string;
  availableModels: HostedModel[];
  onSelectModel: (modelId: string) => void;
  onNewChat: () => void;
  onOpenSettings?: () => void;
  onOpenVoiceMode?: () => void;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  selectedModel,
  availableModels,
  onSelectModel,
  onNewChat,
  onOpenSettings,
  onOpenVoiceMode,
  theme = "light",
  onToggleTheme,
}) => {
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);

  const activeModelObj = availableModels.find((m) => m.id === selectedModel);
  const displayModelName = activeModelObj ? activeModelObj.name : "GPT-OSS 120B (Flagship Deep Intelligence)";
  const displayProvider = activeModelObj ? activeModelObj.provider : "Groq";

  return (
    <header className="h-14 border-b border-gray-100 bg-white/90 backdrop-blur-sm px-6 flex items-center justify-between z-20 select-none transition-colors">
      {/* Model Selector Pill (Left-aligned in main canvas) */}
      <div className="relative">
        <button
          onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
          className="flex items-center space-x-2.5 px-4 py-1.5 rounded-full bg-gray-50/90 hover:bg-gray-100 border border-gray-200/80 text-xs font-semibold text-gray-800 transition-all shadow-sm"
        >
          {/* Emerald Sparkle */}
          <Sparkles className="w-3.5 h-3.5 text-emerald-500 fill-emerald-500/20" />
          <span className="font-medium text-gray-800 tracking-tight">{displayModelName}</span>
          <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 bg-emerald-50 text-emerald-600 rounded-md border border-emerald-200/60">
            {displayProvider}
          </span>
          <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
        </button>

        {modelDropdownOpen && (
          <>
            <div
              className="fixed inset-0 z-30"
              onClick={() => setModelDropdownOpen(false)}
            />
            <div className="absolute top-11 left-0 w-84 bg-white border border-gray-200 rounded-2xl shadow-xl z-40 py-2 overflow-hidden animate-in fade-in zoom-in-95 duration-100">
              <div className="px-4 py-1.5 text-[10px] font-bold text-gray-400 uppercase tracking-wider border-b border-gray-100">
                Select Intelligence Engine
              </div>
              <div className="max-h-72 overflow-y-auto py-1">
                {availableModels.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => {
                      onSelectModel(m.id);
                      setModelDropdownOpen(false);
                    }}
                    className={`w-full text-left px-4 py-2.5 hover:bg-gray-50 transition-colors flex flex-col space-y-0.5 ${
                      m.id === selectedModel ? "bg-emerald-50/50 border-l-2 border-emerald-500" : ""
                    }`}
                  >
                    <span className="text-xs font-bold text-gray-900 flex items-center justify-between">
                      {m.name}
                      <span className="text-[9px] uppercase px-1.5 py-0.5 bg-emerald-50 text-emerald-600 rounded font-semibold border border-emerald-200/60">
                        {m.provider}
                      </span>
                    </span>
                    <span className="text-[11px] text-gray-500 leading-tight">
                      {m.description}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Right Action Controls: Voice, Theme Toggle, + New Chat, Settings */}
      <div className="flex items-center space-x-3 text-xs">
        {/* Voice Mode Button */}
        <button
          onClick={onOpenVoiceMode}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full hover:bg-gray-100 text-gray-700 font-medium transition-all"
        >
          <Radio className="w-3.5 h-3.5 text-gray-600" />
          <span>Voice</span>
        </button>

        {/* Theme Toggle (Moon / Sun) */}
        {onToggleTheme && (
          <button
            onClick={onToggleTheme}
            title={theme === "light" ? "Switch to Dark Mode" : "Switch to Light Mode"}
            className="p-1.5 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors"
          >
            {theme === "light" ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
          </button>
        )}

        {/* + New Chat */}
        <button
          onClick={onNewChat}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full hover:bg-gray-100 text-gray-700 font-medium transition-all"
        >
          <Plus className="w-3.5 h-3.5 text-gray-600" />
          <span>New Chat</span>
        </button>

        {/* Settings */}
        {onOpenSettings && (
          <button
            onClick={onOpenSettings}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full hover:bg-gray-100 text-gray-700 font-medium transition-all"
          >
            <Sliders className="w-3.5 h-3.5 text-gray-600" />
            <span>Settings</span>
          </button>
        )}
      </div>
    </header>
  );
};
