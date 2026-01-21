"use client";

import { useEffect, useState } from "react";
import { completeMicrosoftLogin } from "../../../lib/msAuth";

export default function AuthCallbackPage() {
  const [status, setStatus] = useState("Completing sign-in...");

  useEffect(() => {
    const run = async () => {
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      const state = params.get("state") || "";
      if (!code) {
        setStatus("Missing authorization code.");
        return;
      }
      try {
        await completeMicrosoftLogin(code, state);
        window.location.href = "/dashboard";
      } catch (err) {
        setStatus(err instanceof Error ? err.message : "Login failed.");
      }
    };
    void run();
  }, []);

  return (
    <main className="login-only">
      <div className="hero-card">
        <h1>{status}</h1>
        <p className="status">
          You can close this page if it does not redirect automatically.
        </p>
      </div>
    </main>
  );
}
