"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/** One form for both login and signup - the only difference is the endpoint. */
export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const resp = await fetch(`/api/auth/${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (resp.ok) {
      // New accounts go straight to the questionnaire.
      router.push(mode === "signup" ? "/onboarding" : "/");
      router.refresh();
      return;
    }
    const body = await resp.json().catch(() => null);
    setError(
      typeof body?.detail === "string"
        ? body.detail
        : "Something went wrong. Check your email and password (8+ characters).",
    );
    setBusy(false);
  }

  return (
    <form onSubmit={submit} className="flex w-full max-w-sm flex-col gap-4">
      <label className="flex flex-col gap-1 text-sm font-medium text-zinc-700">
        Email
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded-lg border border-zinc-300 px-3 py-2 text-base text-zinc-900 outline-none focus:border-red-700"
          placeholder="you@terpmail.umd.edu"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-medium text-zinc-700">
        Password
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="rounded-lg border border-zinc-300 px-3 py-2 text-base text-zinc-900 outline-none focus:border-red-700"
          placeholder="8+ characters"
        />
      </label>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <button
        type="submit"
        disabled={busy}
        className="rounded-lg bg-red-700 px-4 py-2.5 font-semibold text-white transition-colors hover:bg-red-800 disabled:opacity-50"
      >
        {busy ? "One moment…" : mode === "login" ? "Log in" : "Create account"}
      </button>
    </form>
  );
}
