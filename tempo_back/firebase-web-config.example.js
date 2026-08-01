/**
 * Firebase **web** client config (browser). Use with `initializeApp` + `sendPasswordResetEmail`
 * for forgot-password (Firebase sends the email). Copy into your frontend env / config.
 *
 * Backend Django only needs the **service account** JSON + FIREBASE_PROJECT_ID for `googleAuth`
 * token verification — not this apiKey on the server for password reset.
 */
export const firebaseConfig = {
  apiKey: "AIzaSyCUivJ2Z5qSPE-2Y1BmlylzhgWGHgu2qSk",
  authDomain: "lipaidox-platform.firebaseapp.com",
  projectId: "lipaidox-platform",
  storageBucket: "lipaidox-platform.firebasestorage.app",
  messagingSenderId: "600690682419",
  appId: "1:600690682419:web:25229a50d9c7b28085d146",
  measurementId: "G-F804R99ES3",
};
