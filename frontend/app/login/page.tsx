import Link from "next/link";

import AuthForm from "../components/AuthForm";

export const metadata = { title: "Log in – NutriTerp" };

export default function LoginPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-zinc-50 px-4">
      <h1 className="text-3xl font-bold tracking-tight text-zinc-900">
        Welcome back, Terp
      </h1>
      <AuthForm mode="login" />
      <p className="text-sm text-zinc-600">
        No account yet?{" "}
        <Link href="/signup" className="font-semibold text-red-700 hover:underline">
          Sign up
        </Link>
      </p>
    </main>
  );
}
