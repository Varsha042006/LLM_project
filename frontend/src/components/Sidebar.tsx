"use client";

import React, { useState, useEffect } from "react";
import { Plus, Search, MessageSquare, Trash2, Edit2, Check, X, Settings, LogOut, PanelLeftClose, User as UserIcon, FileDown, Archive, FileText } from "lucide-react";
import { Chat, User, downloadChat } from "../lib/api";

interface SidebarProps {
  chats: Chat[];
  activeChatId: string | null;
  onSelectChat: (id: string) => void;
  onNewChat: () => void;
  onRenameChat: (id: string, newTitle: string) => void;
  onDeleteChat: (id: string) => void;
  onArchiveChat?: (id: string) => void;
  isSettingsOpen?: boolean;
  user?: User | null;
  onOpenAuth?: () => void;
  onLogout?: () => void;
  onOpenSettings?: () => void;
  onOpenDocumentModal?: () => void;
  documentCount?: number;
  mode?: "chat" | "xray";
  onModeChange?: (mode: "chat" | "xray") => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  chats,
  activeChatId,
  onSelectChat,
  onNewChat,
  onRenameChat,
  onDeleteChat,
  onArchiveChat,
  isSettingsOpen = false,
  user,
  onOpenAuth,
  onLogout,
  onOpenSettings,
  onOpenDocumentModal,
  documentCount = 0,
}) => {
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  // Keyboard shortcut Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onNewChat();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onNewChat]);

  const filteredChats = chats.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  const startRename = (c: Chat, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(c.id);
    setEditTitle(c.title);
  };

  const saveRename = (chatId: string, e: React.MouseEvent | React.FormEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (editTitle.trim()) {
      onRenameChat(chatId, editTitle.trim());
    }
    setEditingId(null);
  };

  const cancelRename = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
  };

  const isPermanentUser = user && user.auth_provider !== "guest";
  const profileName = user?.display_name || "Amrutha.H";
  const profileEmail = user?.email || "amruthah676@gmail.com";
  const avatarLetter = (profileName.trim()[0] || "A").toUpperCase();

  return (
    <aside className="w-64 border-r border-gray-100 bg-[#fbfcfd] flex flex-col h-full select-none transition-colors">
      
      {/* 1. Top Header: Aura PRO & Logo */}
      <div className="p-3.5 flex items-center justify-between border-b border-gray-100/80">
        <div className="flex items-center space-x-2.5">
          {/* Black circle with glowing cosmic orb */}
          <div className="w-9 h-9 rounded-full bg-black flex items-center justify-center shadow-md relative overflow-hidden flex-shrink-0">
            <svg className="w-7 h-7" viewBox="0 0 100 100" fill="none">
              <defs>
                <radialGradient id="auraSidebarOrb" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#38bdf8" />
                  <stop offset="45%" stopColor="#818cf8" />
                  <stop offset="85%" stopColor="#000000" />
                </radialGradient>
              </defs>
              <circle cx="50" cy="50" r="42" fill="url(#auraSidebarOrb)" />
              <ellipse cx="50" cy="50" rx="28" ry="11" stroke="#00f0ff" strokeWidth="2.5" transform="rotate(-25 50 50)" />
              <circle cx="50" cy="50" r="6" fill="#ffffff" />
            </svg>
          </div>

          {/* Title & PRO pill */}
          <div className="flex flex-col">
            <div className="flex items-center space-x-1.5">
              <span className="font-extrabold text-[15px] text-gray-900 tracking-tight">VYNEXA</span>
              <span className="text-[9px] font-extrabold px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 border border-blue-200/60 uppercase tracking-wider">
                PRO
              </span>
            </div>
            <span className="text-[10px] text-gray-400 font-medium -mt-0.5">AI Platform</span>
          </div>
        </div>

        {/* Collapse Icon */}
        <button
          title="Toggle Sidebar"
          className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      {/* 2. Top Action Controls: New Chat & Search */}
      <div className="p-3 space-y-2 border-b border-gray-100">
        {/* + New Chat Button */}
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-white hover:bg-gray-50 border border-gray-200/80 text-xs font-semibold text-gray-800 transition-all shadow-sm hover:shadow group"
        >
          <div className="flex items-center space-x-2">
            <Plus className="w-4 h-4 text-gray-600 group-hover:scale-110 transition-transform" />
            <span>New chat</span>
          </div>
          <span className="text-[10px] text-gray-400 font-mono">Ctrl+K</span>
        </button>

        {/* Search Input */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations..."
            className="w-full bg-white border border-gray-200/80 focus:border-blue-500 rounded-xl pl-8 pr-3 py-1.5 text-xs text-gray-800 placeholder-gray-400 focus:outline-none transition-all shadow-xs"
          />
        </div>
      </div>

      {/* 3. Conversation List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {filteredChats.length === 0 ? (
          <div className="h-full flex items-center justify-center p-4 text-center text-xs text-gray-400">
            {search ? "No matching chats found." : "No conversations yet"}
          </div>
        ) : (
          <>
            <div className="px-2 pt-2 pb-1 text-[10px] font-bold text-gray-400 uppercase tracking-wider">
              TODAY
            </div>
            {filteredChats.map((c) => {
              const isActive = c.id === activeChatId;
              const isEditing = c.id === editingId;

              return (
                <div
                  key={c.id}
                  onClick={() => onSelectChat(c.id)}
                  className={`group relative flex items-center justify-between p-2 rounded-xl text-xs cursor-pointer transition-all ${
                    isActive
                      ? "bg-white text-gray-900 font-semibold shadow-sm border border-gray-200/80"
                      : "text-gray-700 hover:bg-gray-100/70"
                  }`}
                >
                  {isEditing ? (
                    <form
                      onSubmit={(e) => saveRename(c.id, e)}
                      className="flex items-center space-x-1 w-full"
                    >
                      <input
                        type="text"
                        autoFocus
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        className="bg-white border border-blue-500 rounded px-1.5 py-0.5 text-xs text-gray-900 flex-1 focus:outline-none"
                      />
                      <button
                        type="submit"
                        onClick={(e) => saveRename(c.id, e)}
                        className="p-1 text-emerald-600 hover:text-emerald-700"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={cancelRename}
                        className="p-1 text-gray-400 hover:text-red-500"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </form>
                  ) : (
                    <>
                      <div className="flex items-center space-x-2 min-w-0 flex-1 pr-2">
                        <MessageSquare className={`w-3.5 h-3.5 flex-shrink-0 ${isActive ? "text-blue-600" : "text-gray-400"}`} />
                        <span className="truncate">{c.title}</span>
                      </div>

                      {/* Action buttons on hover */}
                      <div className="opacity-0 group-hover:opacity-100 flex items-center space-x-1 flex-shrink-0 transition-opacity">
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            try {
                              await downloadChat(c.id, "pdf");
                            } catch (err: any) {
                              alert(`Failed to export chat: ${err.message || err}`);
                            }
                          }}
                          title="Export Chat as PDF"
                          className="p-1 text-gray-400 hover:text-emerald-600 transition-colors"
                        >
                          <FileDown className="w-3 h-3" />
                        </button>
                        {onArchiveChat && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onArchiveChat(c.id);
                            }}
                            title="Archive Chat"
                            className="p-1 text-gray-400 hover:text-amber-600 transition-colors"
                          >
                            <Archive className="w-3 h-3" />
                          </button>
                        )}
                        <button
                          onClick={(e) => startRename(c, e)}
                          title="Rename Chat"
                          className="p-1 text-gray-400 hover:text-gray-700 transition-colors"
                        >
                          <Edit2 className="w-3 h-3" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteChat(c.id);
                          }}
                          title="Delete Chat"
                          className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* Quick Nav: My documents & Settings (Matching Screenshot Sidebar) */}
      <div className="px-3 py-2 border-t border-gray-100 dark:border-[#262626] space-y-1 bg-white dark:bg-[#111]">
        {onOpenDocumentModal && (
          <button
            onClick={onOpenDocumentModal}
            className="w-full flex items-center space-x-2.5 px-3 py-2 rounded-xl text-xs font-semibold text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#222] transition-colors cursor-pointer"
          >
            <FileText className="w-4 h-4 text-gray-500 dark:text-gray-400" />
            <span>My documents</span>
            {documentCount > 0 && (
              <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-gray-200 dark:bg-[#333] text-gray-600 dark:text-gray-400 font-bold">
                {documentCount}
              </span>
            )}
          </button>
        )}

        {onOpenSettings && (
          <button
            onClick={onOpenSettings}
            className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-xl text-xs font-semibold transition-colors cursor-pointer ${
              isSettingsOpen
                ? "bg-gray-200/90 text-gray-900 font-bold dark:bg-[#2c2c2c] dark:text-white"
                : "text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#222]"
            }`}
          >
            <Settings className="w-4 h-4 text-gray-500 dark:text-gray-400" />
            <span>Settings</span>
          </button>
        )}
      </div>

      {/* 4. Bottom Action: Sign In / Register Button or Profile */}
      <div className="p-3 border-t border-gray-100 bg-white">
        {isPermanentUser ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5 min-w-0 flex-1">
              <div className="w-8 h-8 rounded-full bg-[#334155] text-white flex items-center justify-center text-xs font-bold flex-shrink-0 shadow-sm">
                {avatarLetter}
              </div>
              <div className="flex flex-col min-w-0 truncate">
                <span className="text-xs font-bold text-gray-900 truncate">
                  {profileName}
                </span>
                <span className="text-[10px] text-gray-400 truncate">
                  {profileEmail}
                </span>
              </div>
            </div>
            <div className="flex items-center space-x-1 flex-shrink-0 ml-1">
              {onOpenSettings && (
                <button
                  onClick={onOpenSettings}
                  title="Settings"
                  className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <Settings className="w-3.5 h-3.5" />
                </button>
              )}
              {onLogout && (
                <button
                  onClick={onLogout}
                  title="Logout"
                  className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            className="w-full flex items-center justify-center space-x-2 py-2.5 px-3 rounded-xl border border-gray-200/80 bg-white hover:bg-gray-50 text-xs font-semibold text-gray-700 transition-all shadow-2xs group"
          >
            <UserIcon className="w-4 h-4 text-blue-600 group-hover:scale-105 transition-transform" />
            <span>Sign In / Register</span>
          </button>
        )}
      </div>
    </aside>
  );
};
