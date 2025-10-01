"use client";

import { useState } from "react";
import LayoutShell from "../../components/LayoutShell";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) {
      setMessage("Provide email & password");
      return;
    }
    localStorage.setItem("ai-lona-token", btoa(`${email}:${password}`));
    setMessage("Mock login stored. Protect routes by checking the token.");
    setEmail("");
    setPassword("");
  }

  return (
    <LayoutShell>
      <form className="card" style={{ maxWidth: 420 }} onSubmit={submit}>
        <h2 style={{ marginTop: 0 }}>Login</h2>
        <label>Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" />
        <label style={{ marginTop: 16 }}>Password</label>
        <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" />
        <button className="primary" style={{ marginTop: 24 }} type="submit">
          Sign in
        </button>
        {message && <p style={{ marginTop: 12, color: "#38bdf8" }}>{message}</p>}
      </form>
    </LayoutShell>
  );
}
