"use client";

import React, { useState, useRef } from "react";
import { X, Upload, FileText, Trash2, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { DocumentItem, uploadDocument, deleteDocument, clearAllDocuments } from "../lib/api";

interface DocumentModalProps {
  isOpen: boolean;
  onClose: () => void;
  documents: DocumentItem[];
  onRefreshDocs: () => void;
}

export const DocumentModal: React.FC<DocumentModalProps> = ({
  isOpen,
  onClose,
  documents,
  onRefreshDocs,
}) => {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];
    setUploading(true);
    setError(null);
    setSuccess(null);

    try {
      const doc = await uploadDocument(file);
      setSuccess(`Indexed "${doc.filename}" into ${doc.num_chunks} vector chunks!`);
      onRefreshDocs();
    } catch (err: any) {
      setError(err.message || "Failed to upload document.");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteDocument(id);
      onRefreshDocs();
    } catch (err: any) {
      setError(err.message || "Failed to delete document.");
    }
  };

  const handleClearAll = async () => {
    if (!confirm("Are you sure you want to delete all indexed documents?")) return;
    try {
      await clearAllDocuments();
      onRefreshDocs();
    } catch (err: any) {
      setError(err.message || "Failed to clear documents.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 dark:bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-lg bg-white dark:bg-[#1a1a1a] border border-gray-200 dark:border-[#333333] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-[#2b2b2b]">
          <div className="flex items-center space-x-2">
            <FileText className="w-5 h-5 text-[#10a37f]" />
            <h3 className="font-bold text-gray-900 dark:text-gray-100 text-sm">Knowledge Base & Document RAG</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-[#262626] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto space-y-4">
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

          {/* Upload Dropzone */}
          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-gray-300 hover:border-[#10a37f] dark:border-[#333333] dark:hover:border-[#10a37f] bg-gray-50 hover:bg-gray-100 dark:bg-[#161616] dark:hover:bg-[#1a1a1a] rounded-xl p-6 text-center cursor-pointer transition-all group"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.csv,.json,.md"
              onChange={(e) => handleFileUpload(e.target.files)}
              className="hidden"
            />
            {uploading ? (
              <div className="flex flex-col items-center justify-center space-y-2">
                <Loader2 className="w-7 h-7 text-[#10a37f] animate-spin" />
                <span className="text-xs text-gray-600 dark:text-gray-300 font-medium">Extracting text & indexing vectors...</span>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center space-y-2">
                <div className="w-10 h-10 rounded-full bg-white dark:bg-[#252525] group-hover:bg-[#10a37f]/10 shadow-sm flex items-center justify-center text-gray-600 dark:text-gray-300 group-hover:text-[#10a37f] transition-colors">
                  <Upload className="w-5 h-5" />
                </div>
                <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 group-hover:text-gray-900 dark:group-hover:text-white">
                  Click to upload document
                </div>
                <div className="text-[11px] text-gray-500 dark:text-gray-400">
                  Supported formats: PDF, DOCX, TXT, CSV, JSON
                </div>
              </div>
            )}
          </div>

          {/* Document List */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              <span>Attached Documents ({documents.length})</span>
              {documents.length > 0 && (
                <button
                  onClick={handleClearAll}
                  className="text-red-500 hover:text-red-700 text-[11px] normal-case font-medium"
                >
                  Clear all
                </button>
              )}
            </div>

            {documents.length === 0 ? (
              <div className="p-4 bg-gray-50 dark:bg-[#141414] rounded-xl border border-gray-200 dark:border-[#262626] text-center text-xs text-gray-500 dark:text-gray-400">
                No documents uploaded yet. Upload a document to ask grounded questions.
              </div>
            ) : (
              <div className="space-y-1.5 max-h-56 overflow-y-auto">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between p-2.5 bg-gray-50 dark:bg-[#171717] border border-gray-200 dark:border-[#2b2b2b] rounded-xl text-xs hover:border-gray-300 dark:hover:border-[#383838] transition-colors"
                  >
                    <div className="flex items-center space-x-2.5 min-w-0 pr-2">
                      <FileText className="w-4 h-4 text-[#10a37f] flex-shrink-0" />
                      <div className="flex flex-col min-w-0">
                        <span className="font-medium text-gray-800 dark:text-gray-200 truncate">{doc.filename}</span>
                        <span className="text-[10px] text-gray-500 dark:text-gray-400">
                          {doc.num_chunks} chunks • {Math.round(doc.file_size / 1024)} KB
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDelete(doc.id)}
                      title="Delete document"
                      className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-gray-200 dark:border-[#262626] bg-gray-50 dark:bg-[#141414] flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-white dark:bg-[#252525] hover:bg-gray-100 dark:hover:bg-[#303030] text-xs font-semibold text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-transparent transition-colors shadow-sm"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
