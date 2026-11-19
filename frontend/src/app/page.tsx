"use client";

import React, { useState, useEffect, useRef } from "react";
import { Navbar } from "../components/Navbar";
import { Sidebar } from "../components/Sidebar";
import { ChatArea } from "../components/ChatArea";
import { ChatInput } from "../components/ChatInput";
import { DocumentModal } from "../components/DocumentModal";
import { SettingsModal } from "../components/SettingsModal";
import { AuthModal } from "../components/AuthModal";
import { XRayDrawer } from "../components/XRayDrawer";
import { XRayWorkspace } from "../components/XRayWorkspace";
import { ImageEditorModal } from "../components/ImageEditorModal";
import {
  User,
  Chat,
  Message,
  DocumentItem,
  HostedModel,
  getMe,
  loginGuest,
  removeToken,
  listChats,
  createChat,
  getChatDetail,
  renameChat,
  deleteChat,
  archiveChat,
  listDocuments,
  getAvailableModels,
  sendFeedback,
  streamChatResponse,
} from "../lib/api";

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [activeDocForChat, setActiveDocForChat] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<HostedModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("openai/gpt-oss-120b");

  // Streaming State
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [streamingContent, setStreamingContent] = useState<string>("");
  const [streamingSources, setStreamingSources] = useState<any[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Modals & Drawers
  const [isDocModalOpen, setIsDocModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isXRayOpen, setIsXRayOpen] = useState(false);
  const [xrayText, setXrayText] = useState("What is AI?");
  const [isImageEditorOpen, setIsImageEditorOpen] = useState(false);
  const [editingImageUrl, setEditingImageUrl] = useState<string>("");

  const handleOpenImageEditor = (url: string) => {
    setEditingImageUrl(url);
    setIsImageEditorOpen(true);
  };

  const handleApplyEditToChat = (resultImageUrl: string, editInstruction: string) => {
    if (!activeChatId) return;
    const astMsg: Message = {
      id: `edit-${Date.now()}`,
      chat_id: activeChatId,
      role: "assistant",
      content: `✨ **AI Image Edit Applied**\n\n![${editInstruction}](${resultImageUrl})\n\n**Instruction:** *${editInstruction}*\n[📥 Download Modified Image](${resultImageUrl})`,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, astMsg]);
  };

  // Workspace Mode (Chat vs Neural X-Ray)
  const [workspaceMode, setWorkspaceMode] = useState<"chat" | "xray">("chat");

  // Theme State (defaults to light for clean UI)
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    // Default to clean light mode
    setTheme("light");
    localStorage.setItem("chatgpt_theme", "light");
    document.documentElement.classList.remove("dark");
    document.documentElement.classList.add("light");
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === "light" ? "dark" : "light";
    setTheme(newTheme);
    localStorage.setItem("chatgpt_theme", newTheme);
    document.documentElement.classList.remove("light", "dark");
    document.documentElement.classList.add(newTheme);
  };

  const handleOpenXRay = (text?: string) => {
    if (text && text.trim()) {
      setXrayText(text.trim());
    }
    setWorkspaceMode("xray");
  };

  // Initialize Session
  useEffect(() => {
    initApp();
  }, []);

  const initApp = async () => {
    try {
      // 1. Check or auto-login Guest
      let currentUser = await getMe();
      if (!currentUser) {
        const guestData = await loginGuest();
        currentUser = guestData.user;
      }
      setUser(currentUser);

      // 2. Load models
      const models = await getAvailableModels();
      if (models.length > 0) {
        setAvailableModels(models);
        setSelectedModel(models[0].id);
      }

      // 3. Load chats & documents
      await refreshChats();
      await refreshDocs();
    } catch (err) {
      console.error("Initialization error:", err);
    }
  };

  const refreshChats = async () => {
    try {
      const chatList = await listChats();
      setChats(chatList);
      if (chatList.length > 0 && !activeChatId) {
        selectChat(chatList[0].id);
      }
    } catch (err) {
      console.error("Failed to load chats:", err);
    }
  };

  const refreshDocs = async () => {
    try {
      const docList = await listDocuments();
      setDocuments(docList);
    } catch (err) {
      console.error("Failed to load documents:", err);
    }
  };

  const selectChat = async (chatId: string) => {
    if (isStreaming) {
      handleStopStreaming();
    }
    setActiveChatId(chatId);
    setActiveDocForChat(null);
    try {
      const detail = await getChatDetail(chatId);
      setMessages(detail.messages || []);
      // If the chat title or messages indicate an attached document, activate it for this chat
      if (detail.title && detail.title.startsWith("Doc: ")) {
        setActiveDocForChat(detail.title.replace("Doc: ", "").trim());
      }
    } catch (err) {
      console.error("Failed to load chat details:", err);
    }
  };

  const handleNewChat = () => {
    if (isStreaming) {
      handleStopStreaming();
    }
    setActiveChatId(null);
    setActiveDocForChat(null);
    setMessages([]);
    setStreamingContent("");
    setStreamingSources([]);
  };

  const handleRenameChat = async (chatId: string, newTitle: string) => {
    try {
      const updated = await renameChat(chatId, newTitle);
      setChats((prev) => prev.map((c) => (c.id === chatId ? { ...c, title: updated.title } : c)));
    } catch (err) {
      console.error("Failed to rename chat:", err);
    }
  };

  const handleDeleteChat = async (chatId: string) => {
    try {
      await deleteChat(chatId);
      setChats((prev) => prev.filter((c) => c.id !== chatId));
      if (activeChatId === chatId) {
        handleNewChat();
      }
    } catch (err) {
      console.error("Failed to delete chat:", err);
    }
  };

  const handleArchiveChat = async (chatId: string) => {
    try {
      await archiveChat(chatId);
      setChats((prev) => prev.filter((c) => c.id !== chatId));
      if (activeChatId === chatId) {
        handleNewChat();
      }
    } catch (err) {
      console.error("Failed to archive chat:", err);
    }
  };

  const handleSendMessage = async (text: string, imageUrl?: string, documentName?: string) => {
    if (!text.trim() && !imageUrl && !documentName) return;
    if (isStreaming) return;

    let targetChatId = activeChatId;

    // Create a new chat if none is active
    if (!targetChatId) {
      try {
        const title = text.slice(0, 30).trim() + (text.length > 30 ? "..." : "");
        const newChat = await createChat(title || (documentName ? `Doc: ${documentName}` : "Query"), selectedModel);
        setChats((prev) => [newChat, ...prev]);
        setActiveChatId(newChat.id);
        targetChatId = newChat.id;
      } catch (err) {
        console.error("Failed to auto-create chat:", err);
        return;
      }
    }

    // Add optimistic user message to thread
    let userContent = text;
    if (imageUrl && !text.includes(imageUrl)) {
      userContent = `![Attached Image](${imageUrl})\n\n${text}`;
    }
    if (documentName && !text.includes(documentName)) {
      userContent = `📄 **Attached Document:** \`${documentName}\`\n\n${text}`;
    }

    const userMsg: Message = {
      id: `temp-user-${Date.now()}`,
      chat_id: targetChatId,
      role: "user",
      content: userContent,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    // Setup streaming
    setIsStreaming(true);
    setStreamingContent("");
    setStreamingSources([]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let accumulatedContent = "";

    if (documentName) {
      setActiveDocForChat(documentName);
    }

    // Strict RAG condition: Only use RAG when a document was attached to this prompt
    // or when the user has an active document set for this specific chat.
    // NEVER apply documents to general chats or clean new chats.
    const isDocQuery = Boolean(documentName || activeDocForChat);

    try {
      await streamChatResponse(
        {
          chat_id: targetChatId,
          message: userContent,
          image_url: imageUrl,
          document_name: documentName || activeDocForChat || undefined,
          model_name: selectedModel,
          use_rag: isDocQuery,
        },
        (token) => {
          accumulatedContent += token;
          setStreamingContent(accumulatedContent);
        },
        (meta) => {
          if (meta.sources && meta.sources.length > 0) {
            setStreamingSources(meta.sources);
          }
        },
        controller.signal
      );

      // Finished stream cleanly: re-fetch chat detail for permanent DB message IDs
      if (targetChatId) {
        const detail = await getChatDetail(targetChatId);
        setMessages(detail.messages || []);
      }
      refreshChats();
    } catch (err: any) {
      if (err.name === "AbortError") {
        console.log("Stream stopped by user");
        if (targetChatId) {
          const detail = await getChatDetail(targetChatId);
          setMessages(detail.messages || []);
        }
      } else {
        console.error("Stream error:", err);
        const errorMsg: Message = {
          id: `error-${Date.now()}`,
          chat_id: targetChatId,
          role: "assistant",
          content: `⚠️ Error during response generation: ${err.message || "Endpoint connection failed"}`,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      }
    } finally {
      setIsStreaming(false);
      setStreamingContent("");
      setStreamingSources([]);
      abortControllerRef.current = null;
    }
  };

  const handleStopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
    }
  };

  const handleRegenerate = () => {
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (lastUserMsg) {
      handleSendMessage(lastUserMsg.content);
    }
  };

  const handleFeedback = async (messageId: string, feedback: "like" | "dislike") => {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, feedback } : m))
    );
    try {
      await sendFeedback(messageId, feedback);
    } catch (err) {
      console.error("Failed to send feedback:", err);
    }
  };

  const handleLogout = async () => {
    removeToken();
    setUser(null);
    setChats([]);
    setMessages([]);
    setActiveChatId(null);
    // Re-login as guest for seamless continuity
    const guest = await loginGuest();
    setUser(guest.user);
    refreshChats();
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-white text-gray-900 font-sans">
      {/* Left Sidebar (Full Height Matching Aura Screenshot) */}
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={(id) => {
          setWorkspaceMode("chat");
          selectChat(id);
        }}
        onNewChat={() => {
          setWorkspaceMode("chat");
          handleNewChat();
        }}
        onRenameChat={handleRenameChat}
        onDeleteChat={handleDeleteChat}
        onArchiveChat={handleArchiveChat}
        isSettingsOpen={isSettingsModalOpen}
        user={user}
        onOpenAuth={() => setIsAuthModalOpen(true)}
        onLogout={handleLogout}
        onOpenSettings={() => setIsSettingsModalOpen(true)}
        onOpenDocumentModal={() => setIsDocModalOpen(true)}
        documentCount={documents.length}
        mode={workspaceMode}
        onModeChange={setWorkspaceMode}
      />

      {/* Right Column: Top Navbar + Main Canvas */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Top Navbar */}
        <Navbar
          user={user}
          selectedModel={selectedModel}
          availableModels={availableModels}
          onSelectModel={setSelectedModel}
          onNewChat={handleNewChat}
          onOpenSettings={() => setIsSettingsModalOpen(true)}
          onOpenVoiceMode={() => handleSendMessage("Launch interactive voice conversation mode")}
          theme={theme}
          onToggleTheme={toggleTheme}
        />

        {/* Center Main Viewport */}
        {workspaceMode === "chat" ? (
          <main className="flex-1 flex flex-col h-full overflow-hidden bg-white">
            <ChatArea
              messages={messages}
              isStreaming={isStreaming}
              streamingContent={streamingContent}
              streamingSources={streamingSources}
              onRegenerate={handleRegenerate}
              onSendFeedback={handleFeedback}
              onSelectPrompt={(prompt) => handleSendMessage(prompt)}
              onOpenXRay={handleOpenXRay}
              onOpenImageEditor={handleOpenImageEditor}
            />

            <ChatInput
              onSendMessage={handleSendMessage}
              onStopStreaming={handleStopStreaming}
              onDocumentUploaded={refreshDocs}
              activeChatDocument={activeDocForChat}
              onDetachChatDocument={() => setActiveDocForChat(null)}
              isStreaming={isStreaming}
            />
          </main>
        ) : (
          <main className="flex-1 flex flex-col h-full overflow-hidden bg-[#0d0f12]">
            <XRayWorkspace initialPrompt={xrayText} />
          </main>
        )}
      </div>

      {/* Modals & Drawers */}
      <ImageEditorModal
        isOpen={isImageEditorOpen}
        onClose={() => setIsImageEditorOpen(false)}
        imageUrl={editingImageUrl}
        chatId={activeChatId}
        onApplyEditToChat={handleApplyEditToChat}
      />

      <DocumentModal
        isOpen={isDocModalOpen}
        onClose={() => setIsDocModalOpen(false)}
        documents={documents}
        onRefreshDocs={refreshDocs}
      />

      <SettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        user={user}
        onUserUpdated={(u) => setUser(u)}
        theme={theme}
        onToggleTheme={toggleTheme}
        onChatRestored={() => refreshChats()}
        onSettingsUpdated={async () => {
          const models = await getAvailableModels();
          setAvailableModels(models);
        }}
      />

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onAuthSuccess={(u) => {
          setUser(u);
          refreshChats();
          refreshDocs();
        }}
      />

      <XRayDrawer
        isOpen={isXRayOpen}
        onClose={() => setIsXRayOpen(false)}
        initialText={xrayText}
      />
    </div>
  );
}

