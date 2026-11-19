"use client";

import React, { useState, useRef, useEffect } from "react";
import { Paperclip, ArrowUp, Square, Loader2, Image as ImageIcon, X, FileText, Mic, MicOff, Plus, Radio } from "lucide-react";
import { uploadImage, uploadDocument } from "../lib/api";

interface ChatInputProps {
  onSendMessage: (message: string, imageUrl?: string, documentName?: string) => void;
  onStopStreaming: () => void;
  onOpenFileUpload?: () => void;
  onDocumentUploaded?: () => void;
  activeChatDocument?: string | null;
  onDetachChatDocument?: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  onStopStreaming,
  onOpenFileUpload,
  onDocumentUploaded,
  activeChatDocument,
  onDetachChatDocument,
  isStreaming,
  disabled,
}) => {
  const [input, setInput] = useState("");
  const [attachedImage, setAttachedImage] = useState<{ url: string; filename: string; preview: string } | null>(null);
  const [isUploadingImage, setIsUploadingImage] = useState(false);

  const [attachedDocument, setAttachedDocument] = useState<{
    id?: string;
    filename: string;
    size?: number;
  } | null>(null);
  const [isUploadingDoc, setIsUploadingDoc] = useState(false);
  const [docUploadError, setDocUploadError] = useState<string | null>(null);

  // Voice Input State
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea as user types
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  // Clean up speech recognition on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {}
      }
    };
  }, []);

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const toggleVoiceInput = () => {
    if (typeof window === "undefined") return;

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.");
      return;
    }

    if (isListening) {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {
          console.error("Speech stop error:", e);
        }
      }
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";

      const baseInput = input.trim();

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        let transcript = "";
        for (let i = 0; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        setInput(baseInput ? `${baseInput} ${transcript}` : transcript);
      };

      recognition.onerror = (event: any) => {
        console.error("Speech recognition error:", event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognition.start();
      recognitionRef.current = recognition;
    } catch (err) {
      console.error("Failed to start speech recognition:", err);
      setIsListening(false);
    }
  };

  const handleImageFile = async (file: File) => {
    if (!file || !file.type.startsWith("image/")) return;
    setIsUploadingImage(true);
    const localPreview = URL.createObjectURL(file);
    try {
      const res = await uploadImage(file);
      setAttachedImage({
        url: res.url,
        filename: file.name,
        preview: localPreview,
      });
    } catch (err) {
      console.error("Image upload fallback:", err);
      // Keep local preview so user query still proceeds
      setAttachedImage({
        url: localPreview,
        filename: file.name,
        preview: localPreview,
      });
    } finally {
      setIsUploadingImage(false);
    }
  };

  const handleDocumentFile = async (file: File) => {
    if (!file) return;
    setIsUploadingDoc(true);
    setDocUploadError(null);
    setAttachedDocument({
      filename: file.name,
      size: file.size,
    });

    try {
      const res = await uploadDocument(file);
      setAttachedDocument({
        id: res.id,
        filename: res.filename,
        size: res.size || file.size,
      });
      if (onDocumentUploaded) {
        onDocumentUploaded();
      }
    } catch (err: any) {
      console.error("Document upload error:", err);
      setDocUploadError(err.message || "Failed to upload document");
    } finally {
      setIsUploadingDoc(false);
    }
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if ((!input.trim() && !attachedImage && !attachedDocument) || isStreaming || disabled || isUploadingDoc) return;

    if (isListening && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
      setIsListening(false);
    }

    const docName = attachedDocument?.filename;
    const messageText =
      input.trim() ||
      (attachedDocument
        ? `Please analyze and summarize the attached document: ${attachedDocument.filename}`
        : attachedImage
        ? "Please inspect and describe this attached image in detail."
        : "");
    const imgUrl = attachedImage?.url;

    onSendMessage(messageText, imgUrl, docName);
    setInput("");
    setAttachedImage(null);
    setAttachedDocument(null); // Document chip disappears immediately upon sending prompt!
    setDocUploadError(null);

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    if (docInputRef.current) {
      docInputRef.current.value = "";
    }
    if (imageInputRef.current) {
      imageInputRef.current.value = "";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith("image/")) {
        const file = items[i].getAsFile();
        if (file) {
          e.preventDefault();
          handleImageFile(file);
          break;
        }
      }
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.type.startsWith("image/")) {
        handleImageFile(file);
      } else {
        handleDocumentFile(file);
      }
    }
  };

  const isSendActive = (input.trim().length > 0 || !!attachedImage || !!attachedDocument) && !disabled && !isUploadingDoc;

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      className="p-4 bg-gradient-to-t from-white via-white/95 to-transparent dark:from-[#141414] dark:via-[#141414] dark:to-transparent flex flex-col items-center select-none"
    >
      <div className="w-full max-w-3xl">
        {/* Hidden Native File Input for Documents */}
        <input
          ref={docInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt,.csv,.json,.md"
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleDocumentFile(e.target.files[0]);
            }
          }}
          className="hidden"
        />

        {/* Hidden Native File Input for Images */}
        <input
          ref={imageInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif,image/bmp"
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleImageFile(e.target.files[0]);
            }
          }}
          className="hidden"
        />

        {/* Attached Document Preview Chip */}
        {attachedDocument && (
          <div className="mb-2 p-2 px-3 rounded-2xl bg-white dark:bg-[#1e232e] border border-gray-200 dark:border-[#2b3547] flex items-center justify-between shadow-md dark:shadow-xl max-w-md animate-in fade-in slide-in-from-bottom-2">
            <div className="flex items-center space-x-3 overflow-hidden">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 flex items-center justify-center flex-shrink-0 text-emerald-600 dark:text-emerald-400">
                {isUploadingDoc ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <FileText className="w-5 h-5" />
                )}
              </div>
              <div className="flex flex-col truncate">
                <span className="text-xs font-semibold text-gray-800 dark:text-gray-100 truncate">
                  {attachedDocument.filename}
                </span>
                <span className="text-[11px] text-gray-500 dark:text-gray-400">
                  {isUploadingDoc
                    ? "Indexing document for RAG..."
                    : docUploadError
                    ? `⚠️ ${docUploadError}`
                    : `Document attached${attachedDocument.size ? ` • ${formatFileSize(attachedDocument.size)}` : ""}`}
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                setAttachedDocument(null);
                setDocUploadError(null);
                if (docInputRef.current) docInputRef.current.value = "";
              }}
              className="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-[#2b3548] rounded-full transition-colors ml-2 flex-shrink-0"
              title="Remove document"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Active Chat Knowledge Base Chip (when a document was previously attached to this chat) */}
        {activeChatDocument && !attachedDocument && (
          <div className="mb-2 p-1.5 px-3 rounded-full bg-blue-50/90 dark:bg-blue-950/40 border border-blue-200/80 dark:border-blue-800/60 flex items-center justify-between text-xs text-blue-700 dark:text-blue-300 shadow-xs max-w-md animate-in fade-in">
            <div className="flex items-center space-x-2 truncate">
              <FileText className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
              <span className="truncate">Active Knowledge Base: <strong className="font-semibold">{activeChatDocument}</strong></span>
            </div>
            {onDetachChatDocument && (
              <button
                type="button"
                onClick={onDetachChatDocument}
                className="p-1 hover:bg-blue-100 dark:hover:bg-blue-900/60 rounded-full text-blue-500 hover:text-red-500 transition-colors ml-2 flex-shrink-0"
                title="Detach document from this chat"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        )}

        {/* Attached Image Preview Chip */}
        {attachedImage && (
          <div className="mb-2 p-2 rounded-2xl bg-white dark:bg-[#1e232e] border border-gray-200 dark:border-[#2b3547] flex items-center justify-between shadow-lg dark:shadow-xl max-w-md animate-in fade-in slide-in-from-bottom-2">
            <div className="flex items-center space-x-3 overflow-hidden">
              <div className="relative w-12 h-12 rounded-xl overflow-hidden border border-gray-200 dark:border-[#3b475a] flex-shrink-0 bg-gray-100 dark:bg-black/60 shadow-inner">
                <img src={attachedImage.preview} alt="Attached" className="w-full h-full object-cover" />
                {isUploadingImage && (
                  <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
                    <Loader2 className="w-4 h-4 text-[#00f0ff] animate-spin" />
                  </div>
                )}
              </div>
              <div className="flex flex-col truncate">
                <span className="text-xs font-bold text-gray-800 dark:text-gray-100 truncate">{attachedImage.filename}</span>
                <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                  {isUploadingImage ? "Uploading to Vision API..." : "🖼️ Image attached • Ask queries or request modifications"}
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setAttachedImage(null)}
              className="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-[#2b3548] rounded-full transition-colors ml-2 flex-shrink-0"
              title="Remove attachment"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Floating Input Pill Matching Aura Design */}
        <div className="relative flex items-center bg-white border border-gray-200/90 focus-within:border-blue-500 rounded-full px-3 py-2 shadow-xs transition-all">
          {/* Quick Attach Plus Button */}
          <button
            type="button"
            onClick={() => docInputRef.current?.click()}
            title="Attach File or Document"
            className="w-8 h-8 flex items-center justify-center text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-full transition-colors flex-shrink-0"
          >
            <Plus className="w-4 h-4" />
          </button>

          {/* Quick Image Attach Button */}
          <button
            type="button"
            onClick={() => imageInputRef.current?.click()}
            title="Attach Image"
            className="w-7 h-7 flex items-center justify-center text-gray-400 hover:text-blue-600 hover:bg-gray-50 rounded-full transition-colors flex-shrink-0 -ml-1 mr-1"
          >
            <ImageIcon className="w-3.5 h-3.5" />
          </button>

          {/* Text Input */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            disabled={disabled}
            placeholder={
              isListening
                ? "Listening... Speak clearly..."
                : attachedDocument
                ? `Ask questions about ${attachedDocument.filename}...`
                : attachedImage
                ? "Ask about this image..."
                : "Ask VYNEXA..."
            }
            className="flex-1 bg-transparent text-gray-900 placeholder-gray-400 text-sm px-2.5 py-1 focus:outline-none resize-none max-h-40 overflow-y-auto leading-relaxed"
          />

          {/* Voice Microphone Icon */}
          <button
            type="button"
            onClick={toggleVoiceInput}
            title={isListening ? "Listening... Click to stop" : "Voice input"}
            className={`p-2 rounded-full transition-all flex-shrink-0 mr-1.5 ${
              isListening
                ? "bg-red-500 hover:bg-red-600 text-white animate-pulse"
                : "text-gray-400 hover:text-gray-700 hover:bg-gray-100"
            }`}
          >
            {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>

          {/* Action / Send / Voice Wave Blue Circle Button */}
          {isStreaming ? (
            <button
              type="button"
              onClick={onStopStreaming}
              title="Stop Generation"
              className="w-8 h-8 rounded-full bg-red-600 hover:bg-red-700 text-white flex items-center justify-center transition-all flex-shrink-0 shadow-sm animate-pulse"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          ) : isSendActive ? (
            <button
              type="button"
              onClick={() => handleSubmit()}
              className="w-8 h-8 rounded-full bg-blue-600 hover:bg-blue-700 text-white flex items-center justify-center transition-all flex-shrink-0 shadow-sm shadow-blue-500/20"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={toggleVoiceInput}
              title="Start Voice Session"
              className="w-8 h-8 rounded-full bg-blue-600 hover:bg-blue-700 text-white flex items-center justify-center transition-all flex-shrink-0 shadow-sm shadow-blue-500/20 group"
            >
              <Radio className="w-4 h-4 group-hover:scale-110 transition-transform" />
            </button>
          )}
        </div>

        {/* Footer Disclaimer */}
        <div className="text-center mt-2.5">
          <span className="text-[11px] text-gray-400 font-medium">
            VYNEXA can make mistakes. Verify important information.
          </span>
        </div>
      </div>
    </div>
  );
};
