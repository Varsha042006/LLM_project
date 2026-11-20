"use client";

import React, { useState } from "react";
import { Bot, User as UserIcon, Copy, Check, ThumbsUp, ThumbsDown, RotateCcw, BookOpen, Sparkles, Activity, Volume2, VolumeX, Radio, FileText, Brain, Code, Mic, FileDown, Loader2, Download } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { Message, downloadDocument } from "../lib/api";

interface ChatAreaProps {
  messages: Message[];
  isStreaming: boolean;
  streamingContent: string;
  streamingSources: any[];
  onRegenerate: () => void;
  onSendFeedback: (messageId: string, feedback: "like" | "dislike") => void;
  onSelectPrompt: (prompt: string) => void;
  onOpenXRay?: (text: string) => void;
  onOpenImageEditor?: (imageUrl: string) => void;
}

/**
 * Normalizes raw LLM markdown output to ensure standard CommonMark/GFM table & list rendering:
 * - Fixes single-line concatenated table rows (| Col | Val || Col2 | Val2 |)
 * - Ensures table headers have newline separation
 */
export function normalizeMarkdownContent(content: string): string {
  if (!content) return "";
  let text = content;
  // 1. Separate compressed single-line table rows: | Detail | Info | |---|---| || Row 1 | Val 1 || Row 2 | Val 2 |
  text = text.replace(/\|\s*\|(?=[^\n])/g, "|\n|");
  // 2. Ensure table header separator gets own line if jammed: | Col1 | Col2 ||---|---|
  text = text.replace(/([^\n])\s*(\|(?:\s*[-:]+[-|\s:]*)\|)/g, "$1\n$2\n");
  return text;
}

const createMarkdownComponents = (
  onSelectPrompt?: (prompt: string) => void,
  onOpenImageEditor?: (imageUrl: string) => void
) => ({
  p: ({ children }: any) => {
    return <p className="mb-3 last:mb-0 leading-relaxed text-gray-900 dark:text-gray-100">{children}</p>;
  },
  ul: ({ children }: any) => {
    return (
      <ul className="my-2.5 space-y-1.5 pl-5 list-disc marker:text-[#10a37f] text-gray-800 dark:text-gray-200 leading-relaxed">
        {children}
      </ul>
    );
  },
  ol: ({ children }: any) => {
    return (
      <ol className="my-2.5 space-y-1.5 pl-5 list-decimal marker:text-[#10a37f] text-gray-800 dark:text-gray-200 leading-relaxed">
        {children}
      </ol>
    );
  },
  li: ({ children }: any) => {
    return <li className="leading-relaxed pl-1">{children}</li>;
  },
  h1: ({ children }: any) => (
    <h1 className="text-xl font-bold text-gray-900 dark:text-white mt-5 mb-2.5 first:mt-0 tracking-tight">{children}</h1>
  ),
  h2: ({ children }: any) => (
    <h2 className="text-lg font-bold text-gray-900 dark:text-white mt-4 mb-2 first:mt-0 tracking-tight">{children}</h2>
  ),
  h3: ({ children }: any) => (
    <h3 className="text-sm font-bold text-gray-900 dark:text-white mt-3 mb-1.5 first:mt-0">{children}</h3>
  ),
  strong: ({ children }: any) => (
    <strong className="font-semibold text-gray-900 dark:text-white">{children}</strong>
  ),
  blockquote: ({ children }: any) => (
    <blockquote className="my-3 pl-3.5 border-l-2 border-[#10a37f] text-gray-600 dark:text-gray-400 italic">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-gray-200 dark:border-[#333]" />,
  table: ({ children }: any) => (
    <div className="my-3.5 overflow-x-auto rounded-xl border border-gray-200 dark:border-[#333] shadow-sm">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-[#333] text-xs">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }: any) => (
    <thead className="bg-gray-100/90 dark:bg-[#252525] text-gray-900 dark:text-gray-100 font-semibold">
      {children}
    </thead>
  ),
  tbody: ({ children }: any) => (
    <tbody className="divide-y divide-gray-100 dark:divide-[#2a2a2a] bg-white dark:bg-[#1a1a1a]">
      {children}
    </tbody>
  ),
  tr: ({ children }: any) => (
    <tr className="hover:bg-gray-50/80 dark:hover:bg-[#222222] transition-colors">
      {children}
    </tr>
  ),
  th: ({ children }: any) => (
    <th className="px-4 py-2.5 text-left font-bold text-gray-900 dark:text-gray-100 tracking-wider">
      {children}
    </th>
  ),
  td: ({ children }: any) => (
    <td className="px-4 py-2.5 text-gray-700 dark:text-gray-200 align-top leading-relaxed">
      {children}
    </td>
  ),
  code: ({ inline, className, children, ...props }: any) => {
    if (inline) {
      return (
        <code className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-[#2b2b2b] text-emerald-700 dark:text-emerald-400 font-mono text-[12px] font-medium border border-gray-200/60 dark:border-[#383838]">
          {children}
        </code>
      );
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children }: any) => (
    <pre className="my-3 p-3.5 rounded-xl bg-gray-900 text-gray-100 dark:bg-[#121212] dark:text-gray-200 overflow-x-auto text-xs font-mono border border-gray-800 dark:border-[#2f2f2f] shadow-sm">
      {children}
    </pre>
  ),
  img: ({ src, alt }: any) => {
    return (
      <div className="my-3 rounded-2xl overflow-hidden border border-gray-200 dark:border-[#2b3345] bg-gray-50 dark:bg-[#0c1017] shadow-md max-w-lg group">
        <div className="relative overflow-hidden bg-gray-100 dark:bg-black/50 flex items-center justify-center">
          <img
            src={src}
            alt={alt || "AI Visual Asset"}
            className="w-full h-auto object-cover rounded-2xl transition-transform duration-300 group-hover:scale-[1.01]"
            loading="lazy"
          />
        </div>
      </div>
    );
  }
});

export const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  isStreaming,
  streamingContent,
  streamingSources,
  onRegenerate,
  onSendFeedback,
  onSelectPrompt,
  onOpenXRay,
  onOpenImageEditor,
}) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);
  const [exportingId, setExportingId] = useState<string | null>(null);
  const [exportMenuMsgId, setExportMenuMsgId] = useState<string | null>(null);

  /**
   * Evaluates if a message constitutes a structured document / report / synthesis
   * suitable for one-click publication and export (PDF, Word, Markdown, Text).
   */
  const getDocumentInfo = (content: string) => {
    if (!content || content.length < 100) return null;

    // Detect top-level heading: # Title or ### 📄 Knowledge Base Synthesis or ### 💡 In-Depth Analysis: ...
    const headerMatch = content.match(/^#+\s*(?:📄|📑|💡|🛡️|🧠|⚡|🚀)?\s*([^\n\r#]+)/m);
    let title = headerMatch ? headerMatch[1].trim() : "Generated_Document";
    title = title.replace(/[*_`]/g, "").trim();
    if (!title || title.length < 3) title = "Document";

    // Detect structural markers: multiple sections, bullet lists, tables, or publication headers
    const headings = content.match(/^#{1,4}\s+/gm) || [];
    const hasSections = headings.length >= 2;
    const hasLists = content.includes("\n* ") || content.includes("\n- ") || content.includes("\n1. ");
    const hasTables = content.includes("|") && content.includes("---");
    const isExplicitPublication =
      content.includes("Executive Summary") ||
      content.includes("Overview & Architecture") ||
      content.includes("Knowledge Base Synthesis") ||
      content.includes("In-Depth Analysis") ||
      content.includes("Table of Contents") ||
      content.includes("Key Pillars") ||
      content.includes("Actionable Takeaways");

    if ((hasSections && (hasLists || hasTables)) || isExplicitPublication) {
      return { title, isDocument: true };
    }
    return null;
  };

  /**
   * Downloads the message content as a formatted document file (PDF, Word DOCX, Markdown, or Plain Text).
   */
  const handleExport = async (
    content: string,
    format: "pdf" | "docx" | "md" | "txt",
    msgId: string,
    customTitle?: string
  ) => {
    const docInfo = getDocumentInfo(content);
    let title = customTitle || (docInfo ? docInfo.title : "Document");
    // Clean up title for filename safety
    title = title.replace(/[^\w\s-]/g, "").trim() || "Document";
    const exportKey = `${msgId}-${format}`;

    try {
      setExportingId(exportKey);
      await downloadDocument(content, title, format);
    } catch (err: any) {
      console.error("Document export failed:", err);
      alert(`Document download failed: ${err.message || err}`);
    } finally {
      setExportingId(null);
      setExportMenuMsgId(null);
    }
  };

  const cleanTextForSpeech = (rawText: string): string => {
    return rawText
      // remove markdown images and links
      .replace(/!\[.*?\]\(.*?\)/g, "")
      .replace(/\[(.*?)\]\(.*?\)/g, "$1")
      // remove code blocks
      .replace(/```[\s\S]*?```/g, "Code block omitted.")
      .replace(/`([^`]+)`/g, "$1")
      // remove markdown headers, bold, italics, blockquotes
      .replace(/^#{1,6}\s+/gm, "")
      .replace(/[*_~]{1,3}(.*?)[*_~]{1,3}/g, "$1")
      .replace(/^>\s+/gm, "")
      // remove tables
      .replace(/\|[-:\s|]+\|/g, "")
      .replace(/\|/g, " ")
      // remove bullets and numbering
      .replace(/^\s*[-*+]\s+/gm, "")
      .replace(/^\s*\d+\.\s+/gm, "")
      .replace(/\s+/g, " ")
      .trim();
  };

  const handleToggleSpeech = (messageId: string, content: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      alert("Text-to-speech is not supported in this browser.");
      return;
    }

    if (speakingMessageId === messageId) {
      window.speechSynthesis.cancel();
      setSpeakingMessageId(null);
      return;
    }

    window.speechSynthesis.cancel(); // cancel any active utterance

    const spokenText = cleanTextForSpeech(content);
    if (!spokenText) return;

    const utterance = new SpeechSynthesisUtterance(spokenText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    utterance.onend = () => {
      setSpeakingMessageId(null);
    };

    utterance.onerror = () => {
      setSpeakingMessageId(null);
    };

    setSpeakingMessageId(messageId);
    window.speechSynthesis.speak(utterance);
  };

  React.useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);
  const markdownComponents = React.useMemo(
    () => createMarkdownComponents(onSelectPrompt, onOpenImageEditor),
    [onSelectPrompt, onOpenImageEditor]
  );

  const copyToClipboard = (text: string, id: string) => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text);
      }
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (e) {
      console.error("Clipboard copy error:", e);
    }
  };

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center select-none bg-white transition-colors overflow-y-auto">
        {/* Glowing Neural AI Orb Hero Matching Screenshot */}
        <div className="w-16 h-16 rounded-full bg-black flex items-center justify-center mb-5 shadow-[0_0_35px_rgba(56,189,248,0.4)] relative overflow-hidden group">
          <svg className="w-12 h-12" viewBox="0 0 100 100" fill="none">
            <defs>
              <radialGradient id="auraHeroOrb" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#38bdf8" />
                <stop offset="35%" stopColor="#818cf8" />
                <stop offset="70%" stopColor="#a855f7" />
                <stop offset="100%" stopColor="#000000" />
              </radialGradient>
              <filter id="heroGlow" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>
            <circle cx="50" cy="50" r="42" fill="url(#auraHeroOrb)" filter="url(#heroGlow)" />
            <ellipse cx="50" cy="50" rx="30" ry="12" stroke="#00f0ff" strokeWidth="2.5" transform="rotate(-20 50 50)" />
            <circle cx="50" cy="50" r="6" fill="#ffffff" filter="url(#heroGlow)" />
          </svg>
        </div>

        {/* Title & Subtitle */}
        <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 tracking-tight mb-2">
          What can I help with today?
        </h1>
        <p className="text-sm text-gray-500 max-w-xl mb-6 leading-relaxed">
          VYNEXA is your intelligent AI companion for deep analysis, documents, and real-time conversation.
        </p>

        {/* Feature Badges Row */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-8 max-w-2xl">
          <button
            onClick={() => onSelectPrompt("Launch interactive voice mode with real-time speech synthesis")}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-blue-50/60 hover:bg-blue-50 border border-blue-200/70 text-xs font-semibold text-blue-600 transition-all shadow-2xs"
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Launch Voice Mode</span>
          </button>

          <button
            onClick={() => onSelectPrompt("Upload and index knowledge base documents for intelligent RAG synthesis")}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-teal-50/60 hover:bg-teal-50 border border-teal-200/70 text-xs font-semibold text-teal-700 transition-all shadow-2xs"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Upload Documents (RAG)</span>
          </button>

          <button
            onClick={() => onSelectPrompt("Check cross-chat persistent memory and user preference context")}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-purple-50/60 hover:bg-purple-50 border border-purple-200/70 text-xs font-semibold text-purple-700 transition-all shadow-2xs"
          >
            <Brain className="w-3.5 h-3.5" />
            <span>Cross-Chat Memory</span>
          </button>

          <button
            onClick={() => onSelectPrompt("Demonstrate ultra-fast inference using Groq LPU engine")}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-emerald-50/60 hover:bg-emerald-50 border border-emerald-200/70 text-xs font-semibold text-emerald-700 transition-all shadow-2xs"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Groq Hosted AI</span>
          </button>
        </div>

        {/* 2x2 Feature Action Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 max-w-2xl w-full">
          {/* Card 1: Analyze Knowledge Base */}
          <button
            onClick={() => onSelectPrompt("Analyze my uploaded documents, PDFs, and notes to summarize key findings.")}
            className="text-left p-4 rounded-2xl bg-white hover:bg-gray-50/80 border border-gray-200/90 hover:border-gray-300 shadow-xs hover:shadow-sm transition-all group"
          >
            <div className="flex items-center space-x-2.5 mb-1.5">
              <BookOpen className="w-4 h-4 text-teal-600" />
              <span className="text-sm font-bold text-gray-900 group-hover:text-blue-600 transition-colors">
                Analyze Knowledge Base
              </span>
            </div>
            <p className="text-xs text-gray-500 leading-relaxed">
              Ask questions directly against your uploaded PDF, DOCX, or CSV files.
            </p>
          </button>

          {/* Card 2: Code & Software Architecture */}
          <button
            onClick={() => onSelectPrompt("Help me architect, refactor, and optimize full-stack Next.js and Python code.")}
            className="text-left p-4 rounded-2xl bg-white hover:bg-gray-50/80 border border-gray-200/90 hover:border-gray-300 shadow-xs hover:shadow-sm transition-all group"
          >
            <div className="flex items-center space-x-2.5 mb-1.5">
              <Code className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-bold text-gray-900 group-hover:text-blue-600 transition-colors">
                Code & Software Architecture
              </span>
            </div>
            <p className="text-xs text-gray-500 leading-relaxed">
              Write, debug, and optimize Python, Next.js, and database code.
            </p>
          </button>

          {/* Card 3: Remember Project Context */}
          <button
            onClick={() => onSelectPrompt("Summarize the persistent project context and architectural decisions across sessions.")}
            className="text-left p-4 rounded-2xl bg-white hover:bg-gray-50/80 border border-gray-200/90 hover:border-gray-300 shadow-xs hover:shadow-sm transition-all group"
          >
            <div className="flex items-center space-x-2.5 mb-1.5">
              <Brain className="w-4 h-4 text-purple-600" />
              <span className="text-sm font-bold text-gray-900 group-hover:text-purple-600 transition-colors">
                Remember Project Context
              </span>
            </div>
            <p className="text-xs text-gray-500 leading-relaxed">
              Test cross-chat memory retention across different chat sessions.
            </p>
          </button>

          {/* Card 4: Live Voice & Spoken Chat */}
          <button
            onClick={() => onSelectPrompt("Start an interactive voice conversation with real-time speech synthesis.")}
            className="text-left p-4 rounded-2xl bg-white hover:bg-gray-50/80 border border-gray-200/90 hover:border-gray-300 shadow-xs hover:shadow-sm transition-all group"
          >
            <div className="flex items-center space-x-2.5 mb-1.5">
              <Mic className="w-4 h-4 text-amber-500" />
              <span className="text-sm font-bold text-gray-900 group-hover:text-amber-600 transition-colors">
                Live Voice & Spoken Chat
              </span>
            </div>
            <p className="text-xs text-gray-500 leading-relaxed">
              Start an interactive voice conversation with real-time speech synthesis.
            </p>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6 bg-white dark:bg-[#141414] transition-colors">
      {messages.map((m) => {
        const isUser = m.role === "user";
        const docInfo = !isUser ? getDocumentInfo(m.content) : null;
        let parsedSources: any[] = [];
        if (m.sources) {
          try {
            const parsed = JSON.parse(m.sources);
            if (Array.isArray(parsed)) {
              parsedSources = parsed;
            }
          } catch {
            parsedSources = [];
          }
        }

        return (
          <div
            key={m.id}
            className={`flex flex-col ${isUser ? "items-end" : "items-start"} max-w-4xl mx-auto w-full`}
          >
            <div className={`flex items-start space-x-3 max-w-[85%] ${isUser ? "flex-row-reverse space-x-reverse" : "flex-row"}`}>
              {/* Avatar */}
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm ${
                  isUser
                    ? "bg-gray-200 text-gray-700 dark:bg-[#333333] dark:text-gray-300"
                    : "bg-[#10a37f] text-white"
                }`}
              >
                {isUser ? <UserIcon className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              {/* Message Bubble */}
              <div className="flex flex-col space-y-1">
                <div
                  className={`px-4 py-3 rounded-2xl text-[13.5px] leading-relaxed shadow-sm ${
                    isUser
                      ? "bg-gray-100 text-gray-900 dark:bg-[#2b2b2b] dark:text-white rounded-tr-sm"
                      : "bg-white text-gray-900 border border-gray-200 dark:bg-[#1e1e1e] dark:text-gray-100 dark:border-[#2b2b2b] rounded-tl-sm"
                  }`}
                >
                  <div className="prose dark:prose-invert prose-sm max-w-none break-words text-gray-900 dark:text-gray-100">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw]}
                      components={markdownComponents}
                    >
                      {normalizeMarkdownContent(m.content)}
                    </ReactMarkdown>
                  </div>

                  {/* Cited Sources Box */}
                  {parsedSources.length > 0 && (
                    <details className="mt-3 pt-2.5 border-t border-gray-200 dark:border-[#333333]/80 group">
                      <summary className="text-xs font-semibold text-[#10a37f] hover:underline cursor-pointer flex items-center space-x-1.5 select-none">
                        <BookOpen className="w-3.5 h-3.5" />
                        <span>View Cited Sources ({parsedSources.length})</span>
                      </summary>
                      <div className="mt-2 space-y-1.5">
                        {parsedSources.map((src, sIdx) => (
                          <div
                            key={sIdx}
                            className="bg-gray-50 dark:bg-[#141414] border-l-2 border-[#10a37f] p-2 rounded-r-lg text-xs"
                          >
                            <div className="font-semibold text-gray-800 dark:text-gray-200 flex items-center justify-between">
                              <span>[Source {src.ref}] {src.filename} (Page {src.page})</span>
                              {src.score && (
                                <span className="text-[10px] text-gray-500 dark:text-gray-400">Score: {src.score}</span>
                              )}
                            </div>
                            <div className="text-gray-600 dark:text-gray-400 mt-0.5 line-clamp-2 italic">
                              "{src.snippet}"
                            </div>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>

                {/* Bottom Message Action Bar */}
                <div
                  className={`flex items-center space-x-2 pt-1 text-gray-400 dark:text-gray-500 text-xs ${
                    isUser ? "justify-end" : "justify-start"
                  }`}
                >
                  <button
                    onClick={() => copyToClipboard(m.content, m.id)}
                    title="Copy Text"
                    className="p-1 hover:text-gray-700 dark:hover:text-white transition-colors"
                  >
                    {copiedId === m.id ? (
                      <Check className="w-3.5 h-3.5 text-[#10a37f]" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>

                  {!isUser && (
                    <>
                      {/* Read Aloud (Text to Speech) */}
                      <button
                        onClick={() => handleToggleSpeech(m.id, m.content)}
                        title={speakingMessageId === m.id ? "Stop Reading" : "Read Aloud"}
                        className={`p-1 transition-colors ${
                          speakingMessageId === m.id
                            ? "text-[#10a37f] hover:text-[#0e8c6d]"
                            : "hover:text-gray-700 dark:hover:text-white"
                        }`}
                      >
                        {speakingMessageId === m.id ? (
                          <VolumeX className="w-3.5 h-3.5 animate-pulse text-[#10a37f]" />
                        ) : (
                          <Volume2 className="w-3.5 h-3.5" />
                        )}
                      </button>

                      <button
                        onClick={() => onSendFeedback(m.id, "like")}
                        title="Good Response"
                        className={`p-1 hover:text-gray-700 dark:hover:text-white transition-colors ${
                          m.feedback === "like" ? "text-[#10a37f]" : ""
                        }`}
                      >
                        <ThumbsUp className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => onSendFeedback(m.id, "dislike")}
                        title="Bad Response"
                        className={`p-1 hover:text-gray-700 dark:hover:text-white transition-colors ${
                          m.feedback === "dislike" ? "text-red-500" : ""
                        }`}
                      >
                        <ThumbsDown className="w-3.5 h-3.5" />
                      </button>

                      {onOpenXRay && (
                        <button
                          onClick={() => onOpenXRay(m.content)}
                          title="Open Neural LLM X-Ray Inspection"
                          className="flex items-center space-x-1 px-2 py-0.5 rounded-md hover:bg-gray-100 dark:hover:bg-[#252525] text-gray-500 dark:text-gray-400 hover:text-[#10a37f] dark:hover:text-[#10a37f] transition-colors border border-transparent hover:border-gray-200 dark:hover:border-[#333] ml-1"
                        >
                          <Activity className="w-3 h-3 text-[#10a37f]" />
                          <span className="text-[11px] font-medium">X-Ray</span>
                        </button>
                      )}

                      {/* Export Document Action Menu */}
                      <div className="relative ml-1">
                        <button
                          onClick={() => setExportMenuMsgId(exportMenuMsgId === m.id ? null : m.id)}
                          title="Download this response as a document (PDF, Word, Markdown, Text)"
                          className="flex items-center space-x-1 px-2 py-0.5 rounded-md hover:bg-gray-100 dark:hover:bg-[#252525] text-gray-500 dark:text-gray-400 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors border border-transparent hover:border-gray-200 dark:hover:border-[#333] cursor-pointer"
                        >
                          <FileDown className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                          <span className="text-[11px] font-medium">Export Doc</span>
                        </button>

                        {exportMenuMsgId === m.id && (
                          <>
                            <div
                              className="fixed inset-0 z-30"
                              onClick={() => setExportMenuMsgId(null)}
                            />
                            <div className="absolute left-0 bottom-full mb-1.5 w-48 rounded-xl bg-white dark:bg-[#1e1e1e] border border-gray-200 dark:border-[#333] shadow-xl py-1.5 z-40 animate-in fade-in zoom-in-95">
                              <div className="px-3 py-1 text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider border-b border-gray-100 dark:border-[#2b2b2b] mb-1">
                                Export Format
                              </div>
                              <button
                                onClick={() => handleExport(m.content, "pdf", m.id)}
                                disabled={exportingId === `${m.id}-pdf`}
                                className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200 hover:bg-red-50 dark:hover:bg-red-950/30 hover:text-red-700 dark:hover:text-red-400 flex items-center justify-between cursor-pointer"
                              >
                                <span className="flex items-center gap-1.5">
                                  {exportingId === `${m.id}-pdf` ? <Loader2 className="w-3 h-3 animate-spin text-red-600" /> : <FileDown className="w-3 h-3 text-red-600" />}
                                  <span>PDF Document</span>
                                </span>
                                <span className="text-[10px] text-gray-400">.pdf</span>
                              </button>
                              <button
                                onClick={() => handleExport(m.content, "docx", m.id)}
                                disabled={exportingId === `${m.id}-docx`}
                                className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200 hover:bg-blue-50 dark:hover:bg-blue-950/30 hover:text-blue-700 dark:hover:text-blue-400 flex items-center justify-between cursor-pointer"
                              >
                                <span className="flex items-center gap-1.5">
                                  {exportingId === `${m.id}-docx` ? <Loader2 className="w-3 h-3 animate-spin text-blue-600" /> : <FileDown className="w-3 h-3 text-blue-600" />}
                                  <span>Microsoft Word</span>
                                </span>
                                <span className="text-[10px] text-gray-400">.docx</span>
                              </button>
                              <button
                                onClick={() => handleExport(m.content, "md", m.id)}
                                disabled={exportingId === `${m.id}-md`}
                                className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center justify-between cursor-pointer"
                              >
                                <span className="flex items-center gap-1.5">
                                  {exportingId === `${m.id}-md` ? <Loader2 className="w-3 h-3 animate-spin text-gray-600" /> : <FileDown className="w-3 h-3 text-gray-600" />}
                                  <span>Markdown</span>
                                </span>
                                <span className="text-[10px] text-gray-400">.md</span>
                              </button>
                              <button
                                onClick={() => handleExport(m.content, "txt", m.id)}
                                disabled={exportingId === `${m.id}-txt`}
                                className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center justify-between cursor-pointer"
                              >
                                <span className="flex items-center gap-1.5">
                                  {exportingId === `${m.id}-txt` ? <Loader2 className="w-3 h-3 animate-spin text-gray-500" /> : <FileDown className="w-3 h-3 text-gray-500" />}
                                  <span>Plain Text</span>
                                </span>
                                <span className="text-[10px] text-gray-400">.txt</span>
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}

      {/* Live Streaming Assistant Message */}
      {isStreaming && (
        <div className="flex flex-col items-start max-w-4xl mx-auto w-full">
          <div className="flex items-start space-x-3 max-w-[85%]">
            <div className="w-7 h-7 rounded-lg bg-[#10a37f] text-white flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
              <Bot className="w-4 h-4 animate-pulse" />
            </div>

            <div className="flex flex-col space-y-1">
              <div className="px-4 py-3 rounded-2xl bg-white text-gray-900 border border-gray-200 dark:bg-[#1e1e1e] dark:text-gray-100 dark:border-[#2b2b2b] rounded-tl-sm text-[13.5px] leading-relaxed shadow-sm">
                <div className="prose dark:prose-invert prose-sm max-w-none break-words streaming-cursor text-gray-900 dark:text-gray-100">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw]}
                    components={markdownComponents}
                  >
                    {normalizeMarkdownContent(streamingContent || "...")}
                  </ReactMarkdown>
                </div>

                {streamingSources.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-gray-200 dark:border-[#333333]/80">
                    <div className="text-[11px] font-semibold text-[#10a37f] flex items-center space-x-1">
                      <BookOpen className="w-3 h-3" />
                      <span>Retrieving verified document passages...</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

