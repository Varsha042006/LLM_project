"use client";

import React, { useState } from "react";
import { X, Lock, Mail, User as UserIcon, Loader2, AlertCircle } from "lucide-react";
import { loginEmail, registerEmail, loginGoogle, User } from "../lib/api";
import { signInWithGooglePopup } from "../lib/firebaseAuth";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthSuccess: (user: User) => void;
  initialTab?: "signin" | "register";
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onAuthSuccess,
  initialTab = "signin",
}) => {
  const [mode, setMode] = useState<"signin" | "register">(initialTab);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [showGooglePrompt, setShowGooglePrompt] = useState(false);
  const [googleName, setGoogleName] = useState("");
  const [googleEmail, setGoogleEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleContinueWithGoogle = async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Trigger authentic Firebase Google Popup Sign-In
      const fbAuth = await signInWithGooglePopup();
      // 2. Submit verified Google credentials to backend
      const res = await loginGoogle(fbAuth.name, fbAuth.email, fbAuth.photoUrl, fbAuth.idToken);
      onAuthSuccess(res.user);
      onClose();
    } catch (err: any) {
      console.error("Google sign-in error:", err);
      setError(err.message || "Google sign-in failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleCustomSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!googleEmail) {
      setError("Please provide a Google email address.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await loginGoogle(googleName || googleEmail.split("@")[0], googleEmail);
      onAuthSuccess(res.user);
      setShowGooglePrompt(false);
      onClose();
    } catch (err: any) {
      setError(err.message || "Google sign-in failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError("Please enter your email and password.");
      return;
    }

    if (mode === "register" && password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setLoading(true);
    try {
      if (mode === "signin") {
        const res = await loginEmail(email, password);
        onAuthSuccess(res.user);
        onClose();
      } else {
        const res = await registerEmail(email, password, displayName || email.split("@")[0]);
        onAuthSuccess(res.user);
        onClose();
      }
    } catch (err: any) {
      setError(err.message || (mode === "signin" ? "Invalid email or password." : "Registration failed."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 dark:bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      {/* Modal Dialog Card */}
      <div className="relative w-full max-w-[420px] bg-white rounded-[28px] p-7 sm:p-8 shadow-2xl border border-gray-100 overflow-hidden text-gray-900 select-none">
        
        {/* Top-Right Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 w-8 h-8 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
          title="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Simple Clean Title */}
        <div className="text-center mb-5">
          <h2 className="text-xl font-bold text-gray-900 tracking-tight">
            {mode === "signin" ? "Sign In" : "Create Account"}
          </h2>
        </div>

        {/* Continue with Google Button */}
        <button
          type="button"
          onClick={handleContinueWithGoogle}
          disabled={loading}
          className="w-full py-3 px-4 rounded-full border border-gray-200 hover:bg-gray-50 active:bg-gray-100 text-gray-700 font-semibold text-sm flex items-center justify-center space-x-2.5 shadow-sm transition-all mb-4 group"
        >
          {/* Google Official 4-Color 'G' Logo */}
          <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.8-2.4 3.65v3.03h3.88c2.28-2.1 3.66-5.18 3.66-9.12z" />
            <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.03c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.26v3.13C3.26 21.36 7.33 24 12 24z" />
            <path fill="#FBBC05" d="M5.28 14.29c-.25-.72-.38-1.49-.38-2.29s.13-1.57.38-2.29V6.58H1.26C.46 8.18 0 9.99 0 12s.46 3.82 1.26 5.42l4.02-3.13z" />
            <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.26 6.58l4.02 3.13c.95-2.83 3.6-4.96 6.72-4.96z" />
          </svg>
          <span>Continue with Google</span>
        </button>

        {/* Divider: OR WITH EMAIL */}
        <div className="relative flex items-center justify-center my-4">
          <div className="w-full border-t border-gray-200"></div>
          <span className="absolute bg-white px-3 text-[10px] font-bold text-gray-400 tracking-wider uppercase">
            OR WITH EMAIL
          </span>
        </div>

        {/* Segmented Control Pills: [ Sign In ] [ Create Account ] */}
        <div className="bg-gray-100/90 p-1 rounded-full flex mb-5 border border-gray-200/50">
          <button
            type="button"
            onClick={() => { setMode("signin"); setError(null); }}
            className={`flex-1 py-2 text-xs font-bold rounded-full transition-all ${
              mode === "signin"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-800"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setMode("register"); setError(null); }}
            className={`flex-1 py-2 text-xs font-bold rounded-full transition-all ${
              mode === "register"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-800"
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-4 p-2.5 bg-red-50 border border-red-200 rounded-xl text-xs text-red-600 flex items-start space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-red-500" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "register" && (
            <div>
              <label className="block text-xs font-bold text-gray-900 mb-1.5">
                Full Name
              </label>
              <div className="relative">
                <UserIcon className="w-4 h-4 absolute left-3.5 top-3 text-gray-400" />
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Your Name"
                  className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-2xl text-xs text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                />
              </div>
            </div>
          )}

          {/* Email Address */}
          <div>
            <label className="block text-xs font-bold text-gray-900 mb-1.5">
              Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 absolute left-3.5 top-3 text-gray-400" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-2xl text-xs text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
              />
            </div>
          </div>

          {/* Password */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-bold text-gray-900">
                Password
              </label>
              {mode === "signin" && (
                <button
                  type="button"
                  onClick={() => alert("Password reset link will be sent to your registered email.")}
                  className="text-xs font-semibold text-[#10b981] hover:underline"
                >
                  Forgot Password?
                </button>
              )}
            </div>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3.5 top-3 text-gray-400" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-2xl text-xs text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
              />
            </div>
          </div>

          {/* Submit Button: Royal Blue Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 rounded-2xl bg-[#2563eb] hover:bg-[#1d4ed8] active:bg-[#1e40af] text-white font-bold text-xs shadow-md shadow-blue-500/25 transition-all flex items-center justify-center space-x-2 mt-5 disabled:opacity-60"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Authenticating...</span>
              </>
            ) : (
              <span>{mode === "signin" ? "Sign In" : "Create Account"}</span>
            )}
          </button>
        </form>

        {/* Optional Custom Google Account Switcher */}
        <div className="mt-4 pt-3 text-center border-t border-gray-100">
          {!showGooglePrompt ? (
            <button
              type="button"
              onClick={() => setShowGooglePrompt(true)}
              className="text-[11px] text-gray-400 hover:text-gray-600 transition-colors"
            >
              Sign in with another Google Email?
            </button>
          ) : (
            <form onSubmit={handleGoogleCustomSubmit} className="space-y-2 mt-2">
              <input
                type="email"
                required
                value={googleEmail}
                onChange={(e) => setGoogleEmail(e.target.value)}
                placeholder="Google Email (e.g. varsha@gmail.com)"
                className="w-full px-3 py-1.5 border border-gray-200 rounded-xl text-xs"
              />
              <input
                type="text"
                value={googleName}
                onChange={(e) => setGoogleName(e.target.value)}
                placeholder="Display Name (optional)"
                className="w-full px-3 py-1.5 border border-gray-200 rounded-xl text-xs"
              />
              <div className="flex space-x-2">
                <button
                  type="submit"
                  disabled={loading}
                  className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold"
                >
                  Confirm Google Sign-In
                </button>
                <button
                  type="button"
                  onClick={() => setShowGooglePrompt(false)}
                  className="px-3 py-1.5 bg-gray-100 text-gray-600 rounded-xl text-xs"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
