"use client";

import { startMicrosoftLogin } from "../lib/msAuth";

export default function Home() {
  return (
    <main className="login-page">
      <div className="login-card animate-scale-in">
        <div className="login-logo">
          <img src="/icons/logo_32x32.png" alt="Quilr" className="login-logo-img" />
        </div>
        <h1 className="login-title">Quilr Onboarding</h1>
        <p className="login-subtitle">Welcome to the onboarding portal</p>
        <button
          className="login-button"
          onClick={() => {
            void startMicrosoftLogin();
          }}
        >
          <svg className="login-button-icon" viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="1" y="1" width="9" height="9" fill="#f25022"/>
            <rect x="11" y="1" width="9" height="9" fill="#7fba00"/>
            <rect x="1" y="11" width="9" height="9" fill="#00a4ef"/>
            <rect x="11" y="11" width="9" height="9" fill="#ffb900"/>
          </svg>
          Sign in with Microsoft
        </button>
        <p className="login-footer">Secure authentication powered by Microsoft</p>
      </div>
    </main>
  );
}
