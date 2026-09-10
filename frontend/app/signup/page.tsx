import Link from "next/link";

import AuthForm from "../components/AuthForm";

export const metadata = { title: "Sign up – NutriTerp" };

export default function SignupPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-zinc-50 px-4">
      <h1 className="text-3xl font-bold tracking-tight text-zinc-900">
        Join NutriTerp
      </h1>
      <p className="max-w-sm text-center text-sm text-zinc-600">
        Meal recommendations from the real UMD dining menus, tuned to your
        goals and what you actually like.
      </p>
      <AuthForm mode="signup" />
      <p className="text-sm text-zinc-600">
        Already have an account?{" "}
        <Link href="/login" className="font-semibold text-red-700 hover:underline">
          Log in
        </Link>
      </p>
    </main>
  );
}
