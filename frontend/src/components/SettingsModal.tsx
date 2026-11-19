"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  X,
  Search,
  User as UserIcon,
  Lock,
  Flame,
  Palette,
  Archive,
  Sparkles,
  Pencil,
  Check,
  Trash2,
  RotateCcw,
  Moon,
  Sun,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Upload,
  FileText,
  ChevronRight,
  ShieldCheck,
  LogOut,
  Info,
  GraduationCap,
  FolderGit2,
  Cloud,
  Cpu,
  Copy,
  RefreshCw
} from "lucide-react";
import {
  User,
  UserSettings,
  ActiveSession,
  UsageMetrics,
  Chat,
  MemoryCategory,
  MemoryDetailResponse,
  getSettings,
  updateSettings,
  updateUserProfile,
  changePassword,
  deleteAccount,
  getSessions,
  terminateSession,
  getUsageMetrics,
  getArchivedChats,
  unarchiveChat,
  deleteChat,
  uploadReferencePhoto,
  clearLearnedMemory,
  getStructuredMemory,
  updateStructuredMemory,
  synthesizeMemoryFromChats,
  deleteMemoryCategory
} from "../lib/api";

type SettingsTab = "account" | "security" | "usage" | "appearance" | "archived" | "personalization";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  user?: User | null;
  onUserUpdated?: (user: User) => void;
  onSettingsUpdated?: () => void;
  theme?: "light" | "dark";
  onToggleTheme?: (theme: "light" | "dark") => void;
  onChatRestored?: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  user,
  onUserUpdated,
  onSettingsUpdated,
  theme = "light",
  onToggleTheme,
  onChatRestored,
}) => {
  const [activeTab, setActiveTab] = useState<SettingsTab>("account");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);

  // User Profile State
  const [profileName, setProfileName] = useState(user?.display_name || "sanjana mv");
  const [username, setUsername] = useState(user?.username || "@sanjanamv212");
  const [email, setEmail] = useState(user?.email || "sanjanamv212@gmail.com");
  const [gptProfile, setGptProfile] = useState(user?.gpt_builder_profile || user?.display_name || "sanjana mv");
  const [ageRange, setAgeRange] = useState(user?.age_range || "18 or older");
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  // Password Modal
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);

  // Active Sessions
  const [sessions, setSessions] = useState<ActiveSession[]>([]);

  // Usage Metrics
  const [usageMetrics, setUsageMetrics] = useState<UsageMetrics>({
    plan_name: "VYNEXA AI Free",
    plan_price: "₹0 / month",
    member_since: "Member since November 2026",
    status: "Active",
    monthly_prompts_used: 7,
    monthly_prompts_limit: 1000,
    total_chats: 6,
    prompts_sent: 7,
    ai_responses: 7,
    documents_count: 1,
    pages_indexed: 7,
  });
  const [usageSubTab, setUsageSubTab] = useState<"overview" | "analytics">("overview");

  // Appearance & Response Tuning
  const [currentTheme, setCurrentTheme] = useState<"light" | "dark">(theme);
  const [systemPrompt, setSystemPrompt] = useState(
    "You are a helpful AI assistant. Answer clearly and concisely, and use Markdown when it helps."
  );
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(1050);

  // Archived Chats
  const [archivedChats, setArchivedChats] = useState<Chat[]>([]);
  const [archivedCount, setArchivedCount] = useState(0);

  // Personalization
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [memorySummary, setMemorySummary] = useState(
    "VYNEXA remembers your coding preferences, Python frameworks, and technical architecture guidelines."
  );
  const [memoryDetails, setMemoryDetails] = useState<MemoryDetailResponse | null>(null);
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState<string>("");
  const [isSynthesizing, setIsSynthesizing] = useState<boolean>(false);
  const [memorySearchQuery, setMemorySearchQuery] = useState<string>("");
  const [isMemoryModalOpen, setIsMemoryModalOpen] = useState(false);
  const [warmth, setWarmth] = useState("Warm");
  const [referencePhoto, setReferencePhoto] = useState<string | null>(null);
  const [fullBodyPhoto, setFullBodyPhoto] = useState<string | null>(null);
  const [uploadingPhotoType, setUploadingPhotoType] = useState<"portrait" | "full_body" | null>(null);

  const portraitInputRef = useRef<HTMLInputElement>(null);
  const fullBodyInputRef = useRef<HTMLInputElement>(null);

  // Toast System
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 2800);
  };

  useEffect(() => {
    if (user) {
      setProfileName(user.display_name || "sanjana mv");
      setUsername(user.username || `@${(user.email || "user").split("@")[0]}`);
      setEmail(user.email || "sanjanamv212@gmail.com");
      setGptProfile(user.gpt_builder_profile || user.display_name || "sanjana mv");
      setAgeRange(user.age_range || "18 or older");
    }
  }, [user]);

  useEffect(() => {
    setCurrentTheme(theme);
  }, [theme]);

  useEffect(() => {
    if (isOpen) {
      loadInitialData();
    }
  }, [isOpen]);

  const loadInitialData = async () => {
    setLoading(true);
    try {
      // 1. Load Settings
      const s = await getSettings();
      if (s) {
        setSystemPrompt(s.system_prompt || "You are a helpful AI assistant. Answer clearly and concisely, and use Markdown when it helps.");
        setTemperature(s.temperature ?? 0.7);
        setMaxTokens(s.max_tokens ?? 1050);
        if (s.theme === "dark" || s.theme === "light") {
          setCurrentTheme(s.theme);
        }
        setMemoryEnabled(s.memory_enabled !== false);
        if (s.memory_summary) setMemorySummary(s.memory_summary);
        if (s.tone_warmth) setWarmth(s.tone_warmth);
        if (s.reference_photo_url) setReferencePhoto(s.reference_photo_url);
        if (s.full_body_photo_url) setFullBodyPhoto(s.full_body_photo_url);
      }

      // 1.5. Load Structured Memory
      try {
        const memResp = await getStructuredMemory();
        if (memResp) {
          setMemoryDetails(memResp);
          setMemorySummary(memResp.summary);
        }
      } catch (memErr) {
        console.warn("Could not load structured memory:", memErr);
      }

      // 2. Load Active Sessions
      const sessList = await getSessions();
      setSessions(sessList);

      // 3. Load Usage Metrics
      const usage = await getUsageMetrics();
      setUsageMetrics(usage);

      // 4. Load Archived Chats
      const arch = await getArchivedChats();
      setArchivedChats(arch);
      setArchivedCount(arch.length);
    } catch (e) {
      console.error("Error loading settings initial data:", e);
    } finally {
      setLoading(false);
    }
  };

  // Profile Field Saving
  const handleStartEdit = (field: string, currentVal: string) => {
    setEditingField(field);
    setEditValue(currentVal);
  };

  const handleSaveField = async (field: string) => {
    try {
      const payload: any = {};
      if (field === "name") {
        payload.display_name = editValue.trim();
        setProfileName(editValue.trim());
      } else if (field === "username") {
        payload.username = editValue.trim();
        setUsername(editValue.trim());
      } else if (field === "email") {
        payload.email = editValue.trim();
        setEmail(editValue.trim());
      } else if (field === "gpt_profile") {
        payload.gpt_builder_profile = editValue.trim();
        setGptProfile(editValue.trim());
      } else if (field === "age") {
        payload.age_range = editValue.trim();
        setAgeRange(editValue.trim());
      }

      const updatedUser = await updateUserProfile(payload);
      if (onUserUpdated && updatedUser) {
        onUserUpdated(updatedUser);
      }
      setEditingField(null);
      showToast(`${field.charAt(0).toUpperCase() + field.slice(1)} updated`);
    } catch (err: any) {
      alert(`Update failed: ${err.message || err}`);
    }
  };

  // Password Update
  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    if (newPassword.length < 6) {
      setPasswordError("Password must be at least 6 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match.");
      return;
    }

    try {
      await changePassword(currentPassword, newPassword);
      setIsPasswordModalOpen(false);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      showToast("Password updated successfully");
    } catch (err: any) {
      setPasswordError(err.message || "Failed to change password.");
    }
  };

  // Delete Account
  const handleDeleteAccount = async () => {
    const confirmed = window.confirm(
      "Are you absolutely sure you want to permanently delete your account and all associated chats, documents, and preferences? This action cannot be undone."
    );
    if (!confirmed) return;

    try {
      await deleteAccount();
      alert("Account has been permanently deleted.");
      window.location.reload();
    } catch (err: any) {
      alert(`Account deletion failed: ${err.message || err}`);
    }
  };

  // Session Sign Out
  const handleSignOutSession = async (sessionId: string) => {
    try {
      await terminateSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      showToast("Session signed out");
    } catch (err: any) {
      alert(`Failed to sign out session: ${err.message || err}`);
    }
  };

  // Theme Switching
  const handleSelectTheme = async (newTheme: "light" | "dark") => {
    setCurrentTheme(newTheme);
    if (onToggleTheme) onToggleTheme(newTheme);
    try {
      await updateSettings({ theme: newTheme });
      showToast(newTheme === "dark" ? "Theme set to Dark" : "Theme set to Light");
    } catch (e) {
      console.error(e);
    }
  };

  // Save Response Tuning
  const handleSaveResponseTuning = async () => {
    try {
      await updateSettings({
        system_prompt: systemPrompt,
        temperature,
        max_tokens: maxTokens,
      });
      if (onSettingsUpdated) onSettingsUpdated();
      showToast("Instructions saved");
    } catch (err: any) {
      alert(`Failed to save instructions: ${err.message || err}`);
    }
  };

  // Unarchive Chat
  const handleUnarchive = async (chatId: string) => {
    try {
      await unarchiveChat(chatId);
    } catch (err: any) {
      console.warn("Unarchive API error:", err);
    }
    setArchivedChats((prev) => prev.filter((c) => c.id !== chatId));
    setArchivedCount((prev) => Math.max(0, prev - 1));
    if (onChatRestored) onChatRestored();
    showToast("Chat restored to sidebar");
  };

  // Delete Archived Chat
  const handleDeleteArchived = async (chatId: string) => {
    try {
      await deleteChat(chatId);
    } catch (err: any) {
      console.warn("Delete archived chat API error:", err);
    }
    setArchivedChats((prev) => prev.filter((c) => c.id !== chatId));
    setArchivedCount((prev) => Math.max(0, prev - 1));
    if (onChatRestored) onChatRestored();
    showToast("Archived chat deleted");
  };

  // Personalization: Toggle Memory
  const handleToggleMemory = async (enabled: boolean) => {
    setMemoryEnabled(enabled);
    try {
      await updateSettings({ memory_enabled: enabled });
      showToast(enabled ? "Memory enabled" : "Memory paused");
    } catch (e) {
      console.error(e);
    }
  };

  // Personalization: Warmth Tone
  const handleSelectWarmth = async (val: string) => {
    setWarmth(val);
    try {
      await updateSettings({ tone_warmth: val });
      showToast(`Tone set to ${val}`);
    } catch (e) {
      console.error(e);
    }
  };

  // Personalization: Photo Upload
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>, type: "portrait" | "full_body") => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingPhotoType(type);
    try {
      const res = await uploadReferencePhoto(file, type);
      if (type === "portrait") {
        setReferencePhoto(res.url);
      } else {
        setFullBodyPhoto(res.url);
      }
      showToast("Reference photo uploaded");
    } catch (err: any) {
      alert(`Photo upload failed: ${err.message || err}`);
    } finally {
      setUploadingPhotoType(null);
    }
  };

  // Personalization: Structured Memory Management
  const handleOpenMemoryModal = async () => {
    setIsMemoryModalOpen(true);
    try {
      const memResp = await getStructuredMemory();
      if (memResp) {
        setMemoryDetails(memResp);
        setMemorySummary(memResp.summary);
      }
    } catch (err) {
      console.warn("Error refreshing memory details on modal open:", err);
    }
  };

  const handleSynthesizeMemory = async () => {
    setIsSynthesizing(true);
    try {
      const updated = await synthesizeMemoryFromChats();
      setMemoryDetails(updated);
      setMemorySummary(updated.summary);
      showToast("Memory synthesized from chat history & documents!");
    } catch (err: any) {
      showToast("Failed to re-analyze chat history");
    } finally {
      setIsSynthesizing(false);
    }
  };

  const handleStartEditCategory = (cat: MemoryCategory) => {
    setEditingCategoryId(cat.id);
    setEditingContent(cat.content);
  };

  const handleSaveCategory = async (catId: string) => {
    try {
      const updated = await updateStructuredMemory({
        category_id: catId,
        content: editingContent,
      });
      setMemoryDetails(updated);
      setMemorySummary(updated.summary);
      setEditingCategoryId(null);
      showToast("Memory category updated");
    } catch {
      showToast("Failed to update memory category");
    }
  };

  const handleDeleteCategory = async (catId: string) => {
    if (!window.confirm("Clear this memory section?")) return;
    try {
      const updated = await deleteMemoryCategory(catId);
      setMemoryDetails(updated);
      setMemorySummary(updated.summary);
      showToast("Memory section cleared");
    } catch {
      showToast("Failed to clear memory section");
    }
  };

  const handleCopyCategoryText = (text: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      showToast("Copied to clipboard!");
    }
  };

  const handleResetMemoryToBaseline = async () => {
    if (!window.confirm("Reset memory back to standard baseline profile?")) return;
    try {
      await clearLearnedMemory();
      const updated = await getStructuredMemory();
      setMemoryDetails(updated);
      setMemorySummary(updated.summary);
      showToast("Memory reset to baseline profile");
    } catch {
      showToast("Failed to reset memory");
    }
  };

  const renderCategoryIcon = (iconName: string) => {
    switch (iconName) {
      case "User":
        return <UserIcon className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />;
      case "GraduationCap":
        return <GraduationCap className="w-4 h-4 text-blue-600 dark:text-blue-400" />;
      case "FolderGit2":
        return <FolderGit2 className="w-4 h-4 text-purple-600 dark:text-purple-400" />;
      case "Cloud":
        return <Cloud className="w-4 h-4 text-sky-600 dark:text-sky-400" />;
      case "Cpu":
        return <Cpu className="w-4 h-4 text-amber-600 dark:text-amber-400" />;
      case "Palette":
        return <Palette className="w-4 h-4 text-rose-600 dark:text-rose-400" />;
      default:
        return <Sparkles className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />;
    }
  };

  // Personalization: Clear Memory
  const handleClearMemory = async () => {
    if (!window.confirm("Clear all learned memory and conversation preferences?")) return;
    try {
      await clearLearnedMemory();
      const updated = await getStructuredMemory().catch(() => null);
      if (updated) {
        setMemoryDetails(updated);
        setMemorySummary(updated.summary);
      } else {
        setMemorySummary("VYNEXA memory cleared. The assistant will re-learn preferences over time.");
      }
      setIsMemoryModalOpen(false);
      showToast("Learned memory reset");
    } catch (err: any) {
      alert(`Failed to clear memory: ${err.message || err}`);
    }
  };

  if (!isOpen) return null;

  const avatarInitial = (profileName || "S").charAt(0).toUpperCase();

  // Filter tabs based on search
  const tabsList = [
    { id: "account", label: "Account", icon: UserIcon, group: "ACCOUNT" },
    { id: "security", label: "Security and login", icon: Lock, group: "ACCOUNT" },
    { id: "usage", label: "Usage", icon: Flame, group: "ACCOUNT" },
    { id: "appearance", label: "Appearance", icon: Palette, group: "APP" },
    { id: "archived", label: "Archived chats", icon: Archive, badge: archivedCount, group: "APP" },
    { id: "personalization", label: "Personalization", icon: Sparkles, group: "APP" },
  ];

  const filteredTabs = tabsList.filter(
    (t) =>
      t.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.group.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 md:p-6 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150 select-none">
      <div className="w-full max-w-5xl h-[92vh] max-h-[850px] bg-white dark:bg-[#1a1a1a] rounded-3xl border border-gray-200 dark:border-[#2e2e2e] shadow-2xl flex overflow-hidden relative">
        {/* Close Button top-right */}
        <button
          onClick={onClose}
          title="Close Settings (Esc)"
          className="absolute top-4 right-4 z-40 p-2 text-gray-400 hover:text-gray-700 dark:hover:text-white rounded-full hover:bg-gray-100 dark:hover:bg-[#2b2b2b] transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* ------------------------------------------------------------- */}
        {/* LEFT / MIDDLE SETTINGS NAVIGATION PANE (Matching Screenshot)   */}
        {/* ------------------------------------------------------------- */}
        <div className="w-64 sm:w-72 bg-[#fafafa] dark:bg-[#151515] border-r border-gray-200/80 dark:border-[#262626] flex flex-col p-4 flex-shrink-0">
          {/* Search Settings Input */}
          <div className="relative mb-4">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search settings"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-white dark:bg-[#202020] border border-gray-200 dark:border-[#333] rounded-xl text-xs text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
            />
          </div>

          {/* Profile Mini Header */}
          <div className="mb-4 px-2">
            <span className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider block mb-2">
              PROFILE
            </span>
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center text-xs font-bold shadow-xs">
                {avatarInitial}
              </div>
              <div className="min-w-0 flex-1">
                <span className="text-xs font-bold text-gray-900 dark:text-white block truncate">
                  {profileName}
                </span>
                <span className="text-[10.5px] text-gray-400 block truncate">
                  {email}
                </span>
              </div>
            </div>
          </div>

          {/* Navigation Items (Grouped by ACCOUNT and APP) */}
          <div className="flex-1 overflow-y-auto space-y-4 pr-1">
            {/* ACCOUNT GROUP */}
            <div>
              <span className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider block px-2 mb-1">
                ACCOUNT
              </span>
              <div className="space-y-0.5">
                {filteredTabs
                  .filter((t) => t.group === "ACCOUNT")
                  .map((t) => {
                    const Icon = t.icon;
                    const isActive = activeTab === t.id;
                    return (
                      <button
                        key={t.id}
                        onClick={() => setActiveTab(t.id as SettingsTab)}
                        className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                          isActive
                            ? "bg-gray-200/80 dark:bg-[#2b2b2b] text-gray-900 dark:text-white font-semibold shadow-2xs"
                            : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-[#222]"
                        }`}
                      >
                        <Icon className={`w-4 h-4 ${isActive ? "text-gray-900 dark:text-white" : "text-gray-500 dark:text-gray-400"}`} />
                        <span>{t.label}</span>
                      </button>
                    );
                  })}
              </div>
            </div>

            {/* APP GROUP */}
            <div>
              <span className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider block px-2 mb-1">
                APP
              </span>
              <div className="space-y-0.5">
                {filteredTabs
                  .filter((t) => t.group === "APP")
                  .map((t) => {
                    const Icon = t.icon;
                    const isActive = activeTab === t.id;
                    return (
                      <button
                        key={t.id}
                        onClick={() => setActiveTab(t.id as SettingsTab)}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                          isActive
                            ? "bg-gray-200/80 dark:bg-[#2b2b2b] text-gray-900 dark:text-white font-semibold shadow-2xs"
                            : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-[#222]"
                        }`}
                      >
                        <div className="flex items-center space-x-2.5">
                          <Icon className={`w-4 h-4 ${isActive ? "text-gray-900 dark:text-white" : "text-gray-500 dark:text-gray-400"}`} />
                          <span>{t.label}</span>
                        </div>
                        {t.badge !== undefined && t.badge > 0 && (
                          <span className="w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 text-[10px] font-bold flex items-center justify-center">
                            {t.badge}
                          </span>
                        )}
                      </button>
                    );
                  })}
              </div>
            </div>
          </div>
        </div>

        {/* ------------------------------------------------------------- */}
        {/* RIGHT CONTENT PANE: DYNAMIC VIEW BASED ON ACTIVE TAB          */}
        {/* ------------------------------------------------------------- */}
        <div className="flex-1 overflow-y-auto p-6 md:p-8 bg-white dark:bg-[#1a1a1a]">
          {/* TAB 1: ACCOUNT (Image 1) */}
          {activeTab === "account" && (
            <div className="max-w-2xl space-y-6 animate-in fade-in duration-100">
              <div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">Account</h2>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Review your account details
                </p>
              </div>

              <div>
                <span className="text-xs font-bold text-gray-800 dark:text-gray-200 block mb-2">
                  Details
                </span>

                {/* Account Details Card */}
                <div className="bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] rounded-2xl divide-y divide-gray-100 dark:divide-[#292929] shadow-2xs">
                  {/* Name Row */}
                  <div className="p-3.5 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-gray-900 dark:text-white">Name</div>
                      <div className="text-[11px] text-gray-400">The name associated with your account</div>
                    </div>
                    {editingField === "name" ? (
                      <div className="flex items-center space-x-1.5">
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="px-2.5 py-1 text-xs border rounded-lg dark:bg-[#252525] dark:border-[#444]"
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveField("name")}
                          className="p-1 bg-emerald-600 text-white rounded-md hover:bg-emerald-700"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setEditingField(null)}
                          className="p-1 bg-gray-200 dark:bg-gray-700 rounded-md"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2 text-xs font-medium text-gray-800 dark:text-gray-200">
                        <span>{profileName}</span>
                        <button
                          onClick={() => handleStartEdit("name", profileName)}
                          className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-white"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Username Row */}
                  <div className="p-3.5 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-gray-900 dark:text-white">Username</div>
                      <div className="text-[11px] text-gray-400">Your unique handle on VYNEXA</div>
                    </div>
                    {editingField === "username" ? (
                      <div className="flex items-center space-x-1.5">
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="px-2.5 py-1 text-xs border rounded-lg dark:bg-[#252525] dark:border-[#444]"
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveField("username")}
                          className="p-1 bg-emerald-600 text-white rounded-md hover:bg-emerald-700"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setEditingField(null)}
                          className="p-1 bg-gray-200 dark:bg-gray-700 rounded-md"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2 text-xs font-medium text-gray-800 dark:text-gray-200">
                        <span>{username}</span>
                        <button
                          onClick={() => handleStartEdit("username", username)}
                          className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-white"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Email Row */}
                  <div className="p-3.5 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-gray-900 dark:text-white">Email</div>
                      <div className="text-[11px] text-gray-400">The email address linked to your account</div>
                    </div>
                    {editingField === "email" ? (
                      <div className="flex items-center space-x-1.5">
                        <input
                          type="email"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="px-2.5 py-1 text-xs border rounded-lg dark:bg-[#252525] dark:border-[#444]"
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveField("email")}
                          className="p-1 bg-emerald-600 text-white rounded-md hover:bg-emerald-700"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setEditingField(null)}
                          className="p-1 bg-gray-200 dark:bg-gray-700 rounded-md"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2 text-xs font-medium text-gray-800 dark:text-gray-200">
                        <span>{email}</span>
                        <button
                          onClick={() => handleStartEdit("email", email)}
                          className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-white"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Plan Row */}
                  <div className="p-3.5 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-gray-900 dark:text-white">Plan</div>
                      <div className="text-[11px] text-gray-400">The plan for your current workspace</div>
                    </div>
                    <span className="text-xs font-bold text-emerald-600">Free</span>
                  </div>

                  {/* Age Row */}
                  <div className="p-3.5 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-gray-900 dark:text-white">Age</div>
                      <div className="text-[11px] text-gray-400">The age range used to apply account protections</div>
                    </div>
                    <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{ageRange}</span>
                  </div>

                  {/* GPT Builder Profile Row */}
                  <div className="p-3.5 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-gray-900 dark:text-white">GPT builder profile</div>
                      <div className="text-[11px] text-gray-400">The display name on your GPT builder profile</div>
                    </div>
                    {editingField === "gpt_profile" ? (
                      <div className="flex items-center space-x-1.5">
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="px-2.5 py-1 text-xs border rounded-lg dark:bg-[#252525] dark:border-[#444]"
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveField("gpt_profile")}
                          className="p-1 bg-emerald-600 text-white rounded-md hover:bg-emerald-700"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setEditingField(null)}
                          className="p-1 bg-gray-200 dark:bg-gray-700 rounded-md"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2 text-xs font-medium text-gray-800 dark:text-gray-200">
                        <span>{gptProfile}</span>
                        <button
                          onClick={() => handleStartEdit("gpt_profile", gptProfile)}
                          className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-white"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Password Row */}
                  <div className="p-3.5 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-gray-900 dark:text-white">Password</div>
                      <div className="text-[11px] text-gray-400">Change or update your account password</div>
                    </div>
                    <button
                      onClick={() => setIsPasswordModalOpen(true)}
                      className="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-[#444] bg-white dark:bg-[#252525] hover:bg-gray-50 dark:hover:bg-[#303030] text-xs font-semibold text-gray-800 dark:text-gray-200 transition-colors shadow-2xs"
                    >
                      Change password
                    </button>
                  </div>
                </div>

                {/* Red Box: Delete Account */}
                <div className="mt-4 p-4 rounded-2xl bg-red-50/70 dark:bg-red-950/20 border border-red-200/80 dark:border-red-900/40 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold text-red-600 dark:text-red-400">Delete account</div>
                    <div className="text-[11px] text-gray-500 dark:text-gray-400">
                      Permanently delete your account and its data
                    </div>
                  </div>
                  <button
                    onClick={handleDeleteAccount}
                    className="px-3.5 py-1.5 rounded-xl bg-red-100 hover:bg-red-200 dark:bg-red-900/60 dark:hover:bg-red-900 text-red-700 dark:text-red-200 text-xs font-bold transition-colors cursor-pointer shadow-2xs"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: SECURITY AND LOGIN (Image 2) */}
          {activeTab === "security" && (
            <div className="max-w-2xl space-y-6 animate-in fade-in duration-100">
              <div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">Security and login</h2>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Manage your active sessions and login credentials
                </p>
              </div>

              {/* Card 1: Account Password */}
              <div className="p-4 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] flex items-center justify-between shadow-2xs">
                <div>
                  <div className="text-xs font-bold text-gray-900 dark:text-white">Account password</div>
                  <div className="text-[11px] text-gray-400">Update your sign-in password</div>
                </div>
                <button
                  onClick={() => setIsPasswordModalOpen(true)}
                  className="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-[#444] bg-white dark:bg-[#252525] hover:bg-gray-50 dark:hover:bg-[#303030] text-xs font-semibold text-gray-800 dark:text-gray-200 transition-colors shadow-2xs"
                >
                  Change password
                </button>
              </div>

              {/* Card 2: Active Sessions */}
              <div className="p-4 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] space-y-3.5 shadow-2xs">
                <span className="text-xs font-bold text-gray-900 dark:text-white block">
                  Active sessions
                </span>

                <div className="space-y-3">
                  {sessions.length > 0 ? (
                    sessions.map((sess, idx) => {
                      const isCurrent = idx === 0 || sess.is_current;
                      return (
                        <div
                          key={sess.id}
                          className="flex items-start justify-between pb-3 border-b border-gray-100 dark:border-[#292929] last:border-0 last:pb-0"
                        >
                          <div className="pr-4">
                            <div className="text-[11.5px] font-medium text-gray-800 dark:text-gray-200 break-all leading-tight">
                              {sess.user_agent || "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/157.0.0.0"}
                            </div>
                            <div className="text-[10.5px] text-gray-400 mt-1">
                              {isCurrent ? "Current session • " : ""}Signed in 17/11/2026, 4:10:50 pm
                            </div>
                          </div>

                          {!isCurrent && (
                            <button
                              onClick={() => handleSignOutSession(sess.id)}
                              className="px-3 py-1 rounded-lg border border-gray-200 dark:border-[#444] hover:bg-gray-100 dark:hover:bg-[#252525] text-xs font-semibold text-gray-700 dark:text-gray-300 transition-colors flex-shrink-0"
                            >
                              Sign out
                            </button>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <div className="text-xs text-gray-400 italic">No other active sessions.</div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: USAGE (Image 3) */}
          {activeTab === "usage" && (
            <div className="max-w-2xl space-y-6 animate-in fade-in duration-100">
              <div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">Usage</h2>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Track your real usage, conversation counts, and VYNEXA limits
                </p>
              </div>

              {/* Tabs: Overview & Analytics */}
              <div className="flex items-center space-x-1.5 p-1 bg-gray-100 dark:bg-[#242424] rounded-xl w-fit">
                <button
                  onClick={() => setUsageSubTab("overview")}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    usageSubTab === "overview"
                      ? "bg-white dark:bg-[#1a1a1a] text-gray-900 dark:text-white shadow-2xs"
                      : "text-gray-500 hover:text-gray-800 dark:hover:text-gray-200"
                  }`}
                >
                  Overview
                </button>
                <button
                  onClick={() => setUsageSubTab("analytics")}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    usageSubTab === "analytics"
                      ? "bg-white dark:bg-[#1a1a1a] text-gray-900 dark:text-white shadow-2xs"
                      : "text-gray-500 hover:text-gray-800 dark:hover:text-gray-200"
                  }`}
                >
                  Analytics & Engine
                </button>
              </div>

              {/* Card 1: Your Plan */}
              <div>
                <span className="text-xs font-bold text-gray-800 dark:text-gray-200 block mb-2">
                  Your plan
                </span>
                <div className="p-4 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] flex items-center justify-between shadow-2xs">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-bold text-gray-900 dark:text-white">VYNEXA AI Free</span>
                      <span className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 text-[10px] font-bold">
                        Active
                      </span>
                    </div>
                    <div className="text-[11px] text-gray-400 mt-1">
                      ₹0 / month • Member since November 2026
                    </div>
                  </div>
                  <button className="px-3.5 py-1.5 rounded-xl border border-gray-200 dark:border-[#444] bg-white dark:bg-[#252525] hover:bg-gray-50 dark:hover:bg-[#303030] text-xs font-semibold text-gray-800 dark:text-gray-200 transition-colors shadow-2xs">
                    Plan details
                  </button>
                </div>
              </div>

              {/* Card 2: Monthly Prompt Allowance */}
              <div>
                <span className="text-xs font-bold text-gray-800 dark:text-gray-200 block mb-2">
                  Monthly prompt allowance
                </span>
                <div className="p-4 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] space-y-3 shadow-2xs">
                  <div className="text-[11px] text-gray-400">
                    Track your real-time prompts and conversations with VYNEXA.
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-gray-900 dark:text-white">
                        Monthly usage: {usageMetrics.monthly_prompts_used} / {usageMetrics.monthly_prompts_limit} prompts
                      </span>
                      <span className="font-bold text-emerald-600">
                        {Math.max(0, 100 - Math.round((usageMetrics.monthly_prompts_used / usageMetrics.monthly_prompts_limit) * 100))}% remaining
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full h-2 rounded-full bg-gray-100 dark:bg-[#292929] overflow-hidden">
                      <div
                        className="h-full bg-indigo-600 rounded-full transition-all duration-500"
                        style={{
                          width: `${Math.min(100, (usageMetrics.monthly_prompts_used / usageMetrics.monthly_prompts_limit) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>

                  <div className="text-[10.5px] text-gray-400">
                    Resets on the 1st of every month • Real-time tracking
                  </div>
                </div>
              </div>

              {/* Card 3: Current Account Activity */}
              <div>
                <span className="text-xs font-bold text-gray-800 dark:text-gray-200 block mb-2">
                  Current account activity
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3.5 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] shadow-2xs">
                    <div className="text-[11px] text-gray-400">Total Chats</div>
                    <div className="text-lg font-bold text-gray-900 dark:text-white mt-1">
                      {usageMetrics.total_chats}
                    </div>
                    <div className="text-[10px] text-gray-400 mt-0.5">Active sessions</div>
                  </div>

                  <div className="p-3.5 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] shadow-2xs">
                    <div className="text-[11px] text-gray-400">Prompts Sent</div>
                    <div className="text-lg font-bold text-gray-900 dark:text-white mt-1">
                      {usageMetrics.prompts_sent}
                    </div>
                    <div className="text-[10px] text-gray-400 mt-0.5">User inquiries</div>
                  </div>

                  <div className="p-3.5 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] shadow-2xs">
                    <div className="text-[11px] text-gray-400">AI Responses</div>
                    <div className="text-lg font-bold text-gray-900 dark:text-white mt-1">
                      {usageMetrics.ai_responses}
                    </div>
                    <div className="text-[10px] text-gray-400 mt-0.5">Generated replies</div>
                  </div>

                  <div className="p-3.5 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] shadow-2xs">
                    <div className="text-[11px] text-gray-400">Documents & RAG</div>
                    <div className="text-lg font-bold text-gray-900 dark:text-white mt-1">
                      {usageMetrics.documents_count}
                    </div>
                    <div className="text-[10px] text-gray-400 mt-0.5">{usageMetrics.pages_indexed} pages indexed</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: APPEARANCE (Image 4) */}
          {activeTab === "appearance" && (
            <div className="max-w-2xl space-y-6 animate-in fade-in duration-100">
              {/* Card 1: Theme Preference */}
              <div>
                <span className="text-xs font-bold text-gray-800 dark:text-gray-200 block mb-0.5">
                  Theme preference
                </span>
                <p className="text-[11px] text-gray-400 mb-3">
                  Choose between dark and light appearance modes
                </p>

                <div className="grid grid-cols-2 gap-3.5">
                  {/* Dark Mode Card */}
                  <button
                    onClick={() => handleSelectTheme("dark")}
                    className={`p-5 rounded-2xl border text-center transition-all flex flex-col items-center justify-center cursor-pointer ${
                      currentTheme === "dark"
                        ? "border-emerald-500 bg-white dark:bg-[#222] ring-2 ring-emerald-500/30 shadow-sm"
                        : "border-gray-200 dark:border-[#333] bg-white dark:bg-[#1e1e1e] hover:border-gray-300"
                    }`}
                  >
                    <div className="w-10 h-10 rounded-xl bg-gray-900 text-white flex items-center justify-center mb-2 shadow-xs">
                      <Moon className="w-5 h-5" />
                    </div>
                    <span className="text-xs font-bold text-gray-900 dark:text-white">Dark mode</span>
                    <span className="text-[10.5px] text-gray-400 mt-0.5">Easy on the eyes, true blacks</span>
                  </button>

                  {/* Light Mode Card */}
                  <button
                    onClick={() => handleSelectTheme("light")}
                    className={`p-5 rounded-2xl border text-center transition-all flex flex-col items-center justify-center cursor-pointer ${
                      currentTheme === "light"
                        ? "border-emerald-500 bg-white dark:bg-[#222] ring-2 ring-emerald-500/30 shadow-sm"
                        : "border-gray-200 dark:border-[#333] bg-white dark:bg-[#1e1e1e] hover:border-gray-300"
                    }`}
                  >
                    <div className="w-10 h-10 rounded-xl bg-gray-100 text-gray-800 flex items-center justify-center mb-2 shadow-xs">
                      <Sun className="w-5 h-5" />
                    </div>
                    <span className="text-xs font-bold text-gray-900 dark:text-white">Light mode</span>
                    <span className="text-[10.5px] text-gray-400 mt-0.5">Clean and bright appearance</span>
                  </button>
                </div>
              </div>

              {/* Card 2: Model Response Tuning */}
              <div className="p-5 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] space-y-4 shadow-2xs">
                <div>
                  <span className="text-xs font-bold text-gray-900 dark:text-white block">
                    Model Response Tuning
                  </span>
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-gray-400 block mb-1">
                    System instruction
                  </label>
                  <textarea
                    rows={3}
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                    className="w-full p-3 rounded-xl border border-gray-200 dark:border-[#333] bg-gray-50/50 dark:bg-[#252525] text-xs text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 resize-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-gray-600 dark:text-gray-300 font-medium">Temperature ({temperature})</span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={1.5}
                      step={0.1}
                      value={temperature}
                      onChange={(e) => setTemperature(parseFloat(e.target.value))}
                      className="w-full accent-emerald-600 cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-gray-600 dark:text-gray-300 font-medium">Max tokens ({maxTokens})</span>
                    </div>
                    <input
                      type="range"
                      min={256}
                      max={4096}
                      step={50}
                      value={maxTokens}
                      onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                      className="w-full accent-emerald-600 cursor-pointer"
                    />
                  </div>
                </div>

                <div className="pt-1">
                  <button
                    onClick={handleSaveResponseTuning}
                    className="px-4 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                  >
                    Save instructions
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: ARCHIVED CHATS (Image 5) */}
          {activeTab === "archived" && (
            <div className="max-w-2xl space-y-6 animate-in fade-in duration-100">
              <div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">Archived chats</h2>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Manage conversations that have been archived from your sidebar
                </p>
              </div>

              <div className="space-y-2.5">
                {archivedChats.length > 0 ? (
                  archivedChats.map((c) => (
                    <div
                      key={c.id}
                      className="p-3.5 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] flex items-center justify-between shadow-2xs hover:border-gray-300 transition-all"
                    >
                      <div>
                        <div className="text-xs font-bold text-gray-900 dark:text-white">
                          {c.title}
                        </div>
                        <div className="text-[10.5px] text-gray-400 mt-0.5">
                          Updated {c.updated_at ? new Date(c.updated_at).toLocaleDateString() : "Recently"}
                        </div>
                      </div>

                      <div className="flex items-center space-x-1.5">
                        <button
                          onClick={() => handleUnarchive(c.id)}
                          className="flex items-center space-x-1 px-3 py-1.5 rounded-xl border border-gray-200 dark:border-[#444] bg-white dark:bg-[#252525] hover:bg-gray-50 dark:hover:bg-[#303030] text-xs font-semibold text-gray-800 dark:text-gray-200 transition-colors shadow-2xs cursor-pointer"
                        >
                          <RotateCcw className="w-3 h-3 text-gray-600 dark:text-gray-400" />
                          <span>Unarchive</span>
                        </button>
                        <button
                          onClick={() => handleDeleteArchived(c.id)}
                          title="Permanently delete"
                          className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40 rounded-xl transition-colors cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="p-8 text-center rounded-2xl bg-gray-50/70 dark:bg-[#202020] border border-dashed border-gray-200 dark:border-[#333]">
                    <Archive className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
                    <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">No archived chats</div>
                    <div className="text-[11px] text-gray-400 mt-1">
                      Conversations you archive from your sidebar will appear here.
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 6: PERSONALIZATION (Image 6) */}
          {activeTab === "personalization" && (
            <div className="max-w-2xl space-y-6 animate-in fade-in duration-100">
              <div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">Personalization</h2>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Choose what the assistant remembers and how it responds
                </p>
              </div>

              {/* Card 1: VYNEXA Memory */}
              <div className="p-4 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] space-y-3.5 shadow-2xs">
                <div>
                  <span className="text-xs font-bold text-gray-900 dark:text-white block">VYNEXA memory</span>
                  <span className="text-[11px] text-gray-400">
                    Configure how VYNEXA manages memory. <span className="text-blue-500 cursor-pointer hover:underline">Learn more</span>
                  </span>
                </div>

                {/* Enable Memory Switch */}
                <div className="flex items-center justify-between pt-1 border-t border-gray-100 dark:border-[#292929]">
                  <div className="pr-4">
                    <span className="text-xs font-semibold text-gray-800 dark:text-gray-200 block">Enable memory</span>
                    <span className="text-[11px] text-gray-400">
                      Let VYNEXA personalize your experience based on your chats, files, and connected apps. <span className="text-blue-500 cursor-pointer hover:underline">Learn more</span>
                    </span>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer flex-shrink-0">
                    <input
                      type="checkbox"
                      checked={memoryEnabled}
                      onChange={(e) => handleToggleMemory(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
                  </label>
                </div>

                {/* Memory Summary Row */}
                <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-[#292929]">
                  <div className="pr-4">
                    <span className="text-xs font-semibold text-gray-800 dark:text-gray-200 block">Memory summary</span>
                    <span className="text-[11px] text-gray-400">
                      View an overview of what VYNEXA has learned about you across all conversations. Use custom instructions for information you'd like it to always keep in mind.
                    </span>
                  </div>
                  <button
                    onClick={handleOpenMemoryModal}
                    className="px-3.5 py-1.5 rounded-xl border border-gray-200 dark:border-[#444] bg-white dark:bg-[#252525] hover:bg-gray-50 dark:hover:bg-[#303030] text-xs font-semibold text-gray-800 dark:text-gray-200 transition-colors shadow-2xs flex-shrink-0 cursor-pointer"
                  >
                    Manage
                  </button>
                </div>
              </div>

              {/* Card 2: Reference Photos */}
              <div className="p-4 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] space-y-3.5 shadow-2xs">
                <div>
                  <span className="text-xs font-bold text-gray-900 dark:text-white block">Reference photos</span>
                </div>

                {/* Reference Photo (Portrait) */}
                <div className="flex items-center justify-between pt-1 border-t border-gray-100 dark:border-[#292929]">
                  <div>
                    <span className="text-xs font-semibold text-gray-800 dark:text-gray-200 block">Reference photo</span>
                    <span className="text-[11px] text-gray-400">
                      This is the photo that VYNEXA refers to when you create an image of yourself
                    </span>
                  </div>
                  <div>
                    <input
                      type="file"
                      ref={portraitInputRef}
                      onChange={(e) => handleFileChange(e, "portrait")}
                      className="hidden"
                      accept="image/*"
                    />
                    <button
                      onClick={() => portraitInputRef.current?.click()}
                      disabled={uploadingPhotoType === "portrait"}
                      className="px-3.5 py-1.5 rounded-xl border border-gray-200 dark:border-[#444] bg-white dark:bg-[#252525] hover:bg-gray-50 dark:hover:bg-[#303030] text-xs font-semibold text-gray-800 dark:text-gray-200 transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
                    >
                      {uploadingPhotoType === "portrait" ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        "Upload"
                      )}
                    </button>
                  </div>
                </div>

                {/* Full-body Reference Photo */}
                <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-[#292929]">
                  <div>
                    <span className="text-xs font-semibold text-gray-800 dark:text-gray-200 block">Full-body reference photo</span>
                    <span className="text-[11px] text-gray-400">
                      Used to show how clothing and accessories look on you
                    </span>
                  </div>
                  <div>
                    <input
                      type="file"
                      ref={fullBodyInputRef}
                      onChange={(e) => handleFileChange(e, "full_body")}
                      className="hidden"
                      accept="image/*"
                    />
                    <button
                      onClick={() => fullBodyInputRef.current?.click()}
                      disabled={uploadingPhotoType === "full_body"}
                      className="px-3.5 py-1.5 rounded-xl border border-gray-200 dark:border-[#444] bg-white dark:bg-[#252525] hover:bg-gray-50 dark:hover:bg-[#303030] text-xs font-semibold text-gray-800 dark:text-gray-200 transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
                    >
                      {uploadingPhotoType === "full_body" ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        "Upload"
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* Card 3: Base Style and Tone */}
              <div className="p-4 rounded-2xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#2f2f2f] space-y-3.5 shadow-2xs">
                <div>
                  <span className="text-xs font-bold text-gray-900 dark:text-white block">Base style and tone</span>
                  <span className="text-[11px] text-gray-400">Choose the overall tone of replies</span>
                </div>

                <div className="flex items-center justify-between pt-1 border-t border-gray-100 dark:border-[#292929]">
                  <span className="text-xs font-semibold text-gray-800 dark:text-gray-200">Warmth</span>
                  <select
                    value={warmth}
                    onChange={(e) => handleSelectWarmth(e.target.value)}
                    className="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-[#444] bg-white dark:bg-[#252525] text-xs font-semibold text-gray-800 dark:text-gray-200 focus:outline-none cursor-pointer"
                  >
                    <option value="Warm">Warm</option>
                    <option value="Professional">Professional</option>
                    <option value="Direct">Direct</option>
                    <option value="Concise">Concise</option>
                    <option value="Enthusiastic">Enthusiastic</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ------------------------------------------------------------- */}
        {/* LIVE TOAST NOTIFICATIONS (Matching Image 4)                   */}
        {/* ------------------------------------------------------------- */}
        {toastMessage && (
          <div className="absolute bottom-6 right-6 z-50 flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-white dark:bg-[#252525] border border-gray-200 dark:border-[#383838] shadow-lg text-xs font-semibold text-gray-800 dark:text-gray-100 animate-in slide-in-from-bottom-2 fade-in">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>{toastMessage}</span>
          </div>
        )}

        {/* ------------------------------------------------------------- */}
        {/* CHANGE PASSWORD SUB-MODAL                                     */}
        {/* ------------------------------------------------------------- */}
        {isPasswordModalOpen && (
          <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
            <div className="w-full max-w-sm bg-white dark:bg-[#202020] border border-gray-200 dark:border-[#333] rounded-2xl p-5 shadow-2xl space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-gray-900 dark:text-white">Change Password</h3>
                <button onClick={() => setIsPasswordModalOpen(false)} className="text-gray-400 hover:text-gray-600">
                  <X className="w-4 h-4" />
                </button>
              </div>

              {passwordError && (
                <div className="p-2.5 rounded-lg bg-red-50 text-red-600 text-xs">
                  {passwordError}
                </div>
              )}

              <form onSubmit={handleChangePassword} className="space-y-3">
                <div>
                  <label className="text-[11px] font-semibold text-gray-500 block mb-1">Current Password (optional)</label>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="w-full p-2 rounded-lg border text-xs dark:bg-[#2b2b2b] dark:border-[#444]"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-gray-500 block mb-1">New Password</label>
                  <input
                    type="password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full p-2 rounded-lg border text-xs dark:bg-[#2b2b2b] dark:border-[#444]"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-gray-500 block mb-1">Confirm New Password</label>
                  <input
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full p-2 rounded-lg border text-xs dark:bg-[#2b2b2b] dark:border-[#444]"
                  />
                </div>
                <div className="flex justify-end space-x-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsPasswordModalOpen(false)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-[#2a2a2a]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold"
                  >
                    Update Password
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ------------------------------------------------------------- */}
        {/* MANAGE MEMORY SUB-MODAL (VYNEXA Memory System)                */}
        {/* ------------------------------------------------------------- */}
        {isMemoryModalOpen && (
          <div className="fixed inset-0 z-60 flex items-center justify-center p-3 md:p-6 bg-black/65 backdrop-blur-xs">
            <div className="w-full max-w-3xl max-h-[90vh] bg-white dark:bg-[#1a1a1a] border border-gray-200 dark:border-[#2f2f2f] rounded-3xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
              {/* Header */}
              <div className="p-5 md:p-6 border-b border-gray-100 dark:border-[#282828] flex items-start justify-between flex-shrink-0 bg-gray-50/50 dark:bg-[#1e1e1e]/60">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2.5">
                    <div className="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                      <Sparkles className="w-4 h-4" />
                    </div>
                    <h3 className="text-base font-bold text-gray-900 dark:text-white">
                      VYNEXA Memory
                    </h3>
                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950/70 text-emerald-700 dark:text-emerald-300 text-[10.5px] font-bold border border-emerald-200/50">
                      Active
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 max-w-xl">
                    Learned preferences, projects, technical background, and guidelines synthesized from your chat history and documents.
                  </p>
                </div>
                <button
                  onClick={() => setIsMemoryModalOpen(false)}
                  className="p-1.5 rounded-xl hover:bg-gray-100 dark:hover:bg-[#2c2c2c] text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Action Toolbar */}
              <div className="px-5 py-3 border-b border-gray-100 dark:border-[#262626] bg-white dark:bg-[#1a1a1a] flex flex-wrap items-center justify-between gap-3 flex-shrink-0">
                <div className="relative flex-1 min-w-[200px] max-w-sm">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search memories (e.g. cloud, projects, hardware)..."
                    value={memorySearchQuery}
                    onChange={(e) => setMemorySearchQuery(e.target.value)}
                    className="w-full pl-8 pr-3 py-1.5 text-xs rounded-xl bg-gray-50 dark:bg-[#242424] border border-gray-200 dark:border-[#383838] text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={handleSynthesizeMemory}
                    disabled={isSynthesizing}
                    className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer disabled:opacity-60"
                  >
                    {isSynthesizing ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="w-3.5 h-3.5" />
                    )}
                    <span>{isSynthesizing ? "Analyzing Chats..." : "Re-analyze Chat History"}</span>
                  </button>

                  <button
                    onClick={handleResetMemoryToBaseline}
                    className="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-[#383838] bg-white dark:bg-[#252525] hover:bg-gray-50 dark:hover:bg-[#2e2e2e] text-xs font-semibold text-gray-700 dark:text-gray-300 transition-colors shadow-2xs cursor-pointer"
                  >
                    Reset Baseline
                  </button>
                </div>
              </div>

              {/* Body: Scrollable Categories */}
              <div className="p-5 md:p-6 overflow-y-auto space-y-4 flex-1">
                {memoryDetails && memoryDetails.categories && memoryDetails.categories.length > 0 ? (
                  memoryDetails.categories
                    .filter((cat) => {
                      if (!memorySearchQuery.trim()) return true;
                      const q = memorySearchQuery.toLowerCase();
                      return (
                        cat.title.toLowerCase().includes(q) ||
                        cat.content.toLowerCase().includes(q) ||
                        cat.badge.toLowerCase().includes(q)
                      );
                    })
                    .map((cat) => {
                      const isEditing = editingCategoryId === cat.id;

                      return (
                        <div
                          key={cat.id}
                          className="p-4 rounded-2xl bg-white dark:bg-[#202020] border border-gray-200 dark:border-[#2f2f2f] hover:border-gray-300 dark:hover:border-[#3d3d3d] transition-all shadow-2xs space-y-3"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2.5">
                              <div className="p-1.5 rounded-lg bg-gray-50 dark:bg-[#2a2a2a] border border-gray-100 dark:border-[#383838]">
                                {renderCategoryIcon(cat.icon)}
                              </div>
                              <div>
                                <h4 className="text-xs font-bold text-gray-900 dark:text-white">
                                  {cat.title}
                                </h4>
                                <span className="text-[10px] text-gray-400 font-medium">
                                  {cat.badge}
                                </span>
                              </div>
                            </div>

                            <div className="flex items-center space-x-1.5">
                              <button
                                onClick={() => handleCopyCategoryText(cat.content)}
                                title="Copy content"
                                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#2c2c2c] transition-colors cursor-pointer"
                              >
                                <Copy className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() =>
                                  isEditing
                                    ? setEditingCategoryId(null)
                                    : handleStartEditCategory(cat)
                                }
                                title="Edit section"
                                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#2c2c2c] transition-colors cursor-pointer"
                              >
                                <Pencil className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleDeleteCategory(cat.id)}
                                title="Clear section"
                                className="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors cursor-pointer"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>

                          {isEditing ? (
                            <div className="space-y-2 pt-1">
                              <textarea
                                rows={4}
                                value={editingContent}
                                onChange={(e) => setEditingContent(e.target.value)}
                                className="w-full p-3 rounded-xl border border-gray-200 dark:border-[#383838] bg-gray-50 dark:bg-[#252525] text-xs text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 resize-none font-normal leading-relaxed"
                              />
                              <div className="flex items-center justify-end space-x-2">
                                <button
                                  onClick={() => setEditingCategoryId(null)}
                                  className="px-3 py-1 rounded-lg text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-[#2c2c2c]"
                                >
                                  Cancel
                                </button>
                                <button
                                  onClick={() => handleSaveCategory(cat.id)}
                                  className="px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs"
                                >
                                  Save Section
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="p-3 rounded-xl bg-gray-50/70 dark:bg-[#1a1a1a]/70 border border-gray-100 dark:border-[#282828] text-xs text-gray-700 dark:text-gray-200 leading-relaxed font-normal whitespace-pre-wrap select-text">
                              {cat.content || (
                                <span className="text-gray-400 italic">No notes recorded in this category yet.</span>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })
                ) : (
                  <div className="p-4 rounded-xl bg-gray-50 dark:bg-[#222] text-xs text-gray-700 dark:text-gray-200 leading-relaxed whitespace-pre-wrap">
                    {memorySummary}
                  </div>
                )}

                {/* Dive Deeper Section */}
                <div className="p-4 rounded-2xl bg-gradient-to-br from-emerald-500/5 via-teal-500/5 to-transparent border border-emerald-500/20 dark:border-emerald-500/15 space-y-2">
                  <div className="flex items-center space-x-2">
                    <Sparkles className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    <h5 className="text-xs font-bold text-gray-900 dark:text-white">
                      Dive Deeper: Contextual Memory Engine
                    </h5>
                  </div>
                  <p className="text-[11px] text-gray-600 dark:text-gray-300 leading-relaxed">
                    VYNEXA automatically references this memory to tailor every conversation:
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 pt-1">
                    <div className="p-2.5 rounded-xl bg-white dark:bg-[#202020] border border-gray-100 dark:border-[#2f2f2f] text-[10.5px]">
                      <span className="font-bold text-gray-900 dark:text-white block mb-0.5">
                        💻 Windows 11 Dell Setup
                      </span>
                      <span className="text-gray-500 dark:text-gray-400">
                        Provides concrete PowerShell scripts and clean terminal instructions.
                      </span>
                    </div>
                    <div className="p-2.5 rounded-xl bg-white dark:bg-[#202020] border border-gray-100 dark:border-[#2f2f2f] text-[10.5px]">
                      <span className="font-bold text-gray-900 dark:text-white block mb-0.5">
                        🎓 GM University & PBL
                      </span>
                      <span className="text-gray-500 dark:text-gray-400">
                        Contextualizes guidance around Falcon PBL Hub and college presentation requirements.
                      </span>
                    </div>
                    <div className="p-2.5 rounded-xl bg-white dark:bg-[#202020] border border-gray-100 dark:border-[#2f2f2f] text-[10.5px]">
                      <span className="font-bold text-gray-900 dark:text-white block mb-0.5">
                        ☁️ Cloud & IoT Awareness
                      </span>
                      <span className="text-gray-500 dark:text-gray-400">
                        Preserves AWS Free Tier caution, ESP8266 architectures, and fraud detection contexts.
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Modal Footer */}
              <div className="p-4 border-t border-gray-100 dark:border-[#282828] bg-gray-50/50 dark:bg-[#1e1e1e]/60 flex items-center justify-between flex-shrink-0">
                <button
                  onClick={handleClearMemory}
                  className="px-3.5 py-1.5 rounded-xl bg-red-100 hover:bg-red-200 text-red-700 text-xs font-bold transition-colors cursor-pointer"
                >
                  Clear All Memory
                </button>
                <button
                  onClick={() => setIsMemoryModalOpen(false)}
                  className="px-4 py-1.5 rounded-xl bg-gray-900 hover:bg-black text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
