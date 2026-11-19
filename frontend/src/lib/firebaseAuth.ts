// Client-side Firebase Authentication Manager for Next.js

export const FIREBASE_CONFIG = {
  apiKey: "AIzaSyAvalzQ3T-XfG5wT45hV3se6EvsM9PjPzU",
  authDomain: "localgpt-pro-45558.firebaseapp.com",
  projectId: "localgpt-pro-45558",
  storageBucket: "localgpt-pro-45558.firebasestorage.app",
  messagingSenderId: "428746563248",
  appId: "1:428746563248:web:09a472d6ca0035ac652575",
};

declare global {
  interface Window {
    firebase: any;
  }
}

/**
 * Ensures Firebase Compat SDKs are loaded onto the window.
 */
export async function loadFirebaseSdk(): Promise<any> {
  if (typeof window === "undefined") return null;

  if (window.firebase && window.firebase.auth) {
    return window.firebase;
  }

  return new Promise((resolve, reject) => {
    // 1. Load firebase-app-compat.js
    const loadScript = (src: string): Promise<void> => {
      return new Promise((res, rej) => {
        if (document.querySelector(`script[src="${src}"]`)) {
          res();
          return;
        }
        const script = document.createElement("script");
        script.src = src;
        script.async = true;
        script.onload = () => res();
        script.onerror = () => rej(new Error(`Failed to load ${src}`));
        document.head.appendChild(script);
      });
    };

    loadScript("https://www.gstatic.com/firebasejs/10.8.0/firebase-app-compat.js")
      .then(() => loadScript("https://www.gstatic.com/firebasejs/10.8.0/firebase-auth-compat.js"))
      .then(() => {
        if (window.firebase) {
          resolve(window.firebase);
        } else {
          reject(new Error("Firebase SDK loaded but window.firebase is missing"));
        }
      })
      .catch(reject);
  });
}

/**
 * Triggers a Google Popup Sign-In using Firebase Auth.
 */
export async function signInWithGooglePopup(): Promise<{
  idToken: string;
  name: string;
  email: string;
  photoUrl: string;
  uid: string;
}> {
  const firebase = await loadFirebaseSdk();
  if (!firebase) {
    throw new Error("Firebase SDK could not be initialized.");
  }

  // Initialize app if not already initialized
  if (!firebase.apps.length) {
    firebase.initializeApp(FIREBASE_CONFIG);
  }

  const provider = new firebase.auth.GoogleAuthProvider();
  // Always force account selection prompt
  provider.setCustomParameters({ prompt: "select_account" });

  try {
    const result = await firebase.auth().signInWithPopup(provider);
    const fbUser = result.user;
    const idToken = await fbUser.getIdToken();

    return {
      idToken,
      name: fbUser.displayName || fbUser.email?.split("@")[0] || "Google User",
      email: fbUser.email || "",
      photoUrl: fbUser.photoURL || "",
      uid: fbUser.uid,
    };
  } catch (err: any) {
    console.error("Firebase Google Sign-In error:", err);
    if (err.code === "auth/popup-closed-by-user") {
      throw new Error("Sign-in cancelled. You closed the Google sign-in window.");
    }
    if (err.code === "auth/popup-blocked") {
      throw new Error("Pop-up blocked by your browser. Please allow popups for localhost.");
    }
    if (err.code === "auth/unauthorized-domain") {
      throw new Error(
        `Firebase domain unauthorized: ${window.location.hostname}. Please add '${window.location.hostname}' to Firebase Authorized Domains.`
      );
    }
    throw new Error(err.message || "Google authentication failed.");
  }
}

