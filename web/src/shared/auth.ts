/* Optional Firebase Authentication.
 * If VITE_FIREBASE_API_KEY is set at build time, users sign in with Google and every API call carries a
 * Firebase ID token (backend must run with AUTH_MODE=firebase). Otherwise the app runs in open demo mode. */
import type { Auth, User } from "firebase/auth";

const cfg = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY as string | undefined,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN as string | undefined,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID as string | undefined,
  appId: import.meta.env.VITE_FIREBASE_APP_ID as string | undefined,
};

export const firebaseEnabled = Boolean(cfg.apiKey);
let authPromise: Promise<Auth> | null = null;

async function auth(): Promise<Auth> {
  if (!authPromise) {
    authPromise = (async () => {
      const { initializeApp } = await import("firebase/app");
      const { getAuth } = await import("firebase/auth");
      return getAuth(initializeApp(cfg));
    })();
  }
  return authPromise;
}

export async function getIdToken(): Promise<string | null> {
  if (!firebaseEnabled) return null;
  const a = await auth();
  return a.currentUser ? a.currentUser.getIdToken() : null;
}

export async function signIn(): Promise<void> {
  const { GoogleAuthProvider, signInWithPopup } = await import("firebase/auth");
  await signInWithPopup(await auth(), new GoogleAuthProvider());
}

export async function signOut(): Promise<void> {
  const { signOut: so } = await import("firebase/auth");
  await so(await auth());
}

export async function onUser(cb: (u: User | null) => void): Promise<() => void> {
  const { onAuthStateChanged } = await import("firebase/auth");
  return onAuthStateChanged(await auth(), cb);
}
