"use client";

import { startMicrosoftLogin } from "../lib/msAuth";

export default function Home() {
  return (
    <main className="login-only">
      <button
        className="button"
        onClick={() => {
          void startMicrosoftLogin();
        }}
      >
        Login with Microsoft
      </button>
    </main>
  );
}
