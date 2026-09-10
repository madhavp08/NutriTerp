"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

/**
 * Home. For now it only proves the auth loop end to end; the meal
 * suggestions dashboard replaces the logged-in view in a later feature.
 */
export default function Home() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/auth/me")
      .then((r) => (r.ok ? r.json() : null))
      .then((body) => setEmail(body?.email ?? null))
      .finally(() => setLoading(false));
  }, []);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    setEmail(null);
    router.refresh();
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-zinc-50 px-4">
      <h1 className="text-4xl font-bold tracking-tight text-zinc-900">
        Nutri<span className="text-red-700">Terp</span>
      </h1>
      <p className="max-w-md text-center text-zinc-600">
        UMD dining hall meals, ranked for you.
      </p>

      {loading ? (
        <p className="text-sm text-zinc-400">Checking your session…</p>
      ) : email ? (
        <div className="flex flex-col items-center gap-3">
          <p className="text-zinc-800">
            Logged in as <span className="font-semibold">{email}</span>
          </p>
          <button
            onClick={logout}
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100"
          >
            Log out
          </button>
        </div>
      ) : (
        <div className="flex gap-3">
          <Link
            href="/signup"
            className="rounded-lg bg-red-700 px-5 py-2.5 font-semibold text-white hover:bg-red-800"
          >
            Sign up
          </Link>
          <Link
            href="/login"
            className="rounded-lg border border-zinc-300 px-5 py-2.5 font-semibold text-zinc-800 hover:bg-zinc-100"
          >
            Log in
          </Link>
        </div>
      )}
    </main>
  );
}
