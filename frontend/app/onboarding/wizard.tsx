"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

/**
 * Five-step questionnaire. Answers accumulate in one state object and are
 * saved with a single PUT /api/profile at the end. Body metrics are asked
 * in feet/inches and pounds (natural for UMD students) and converted to
 * cm/kg on save, because the backend and the formula are metric.
 */

const DIETS = [
  { id: "none", label: "No restrictions", hint: "I eat everything" },
  { id: "vegetarian", label: "Vegetarian", hint: "No meat or fish" },
  { id: "vegan", label: "Vegan", hint: "No animal products" },
  { id: "halal", label: "Halal", hint: "Halal-friendly meals only" },
] as const;

const ALLERGENS = [
  "dairy", "egg", "fish", "shellfish", "gluten",
  "soy", "sesame", "nuts", "coconut",
] as const;

const GOALS = [
  { id: "lose", label: "Lose weight", hint: "Lighter, high-protein picks" },
  { id: "maintain", label: "Maintain", hint: "Balanced everyday meals" },
  { id: "gain", label: "Gain muscle", hint: "More calories and protein" },
] as const;

const ACTIVITY = [
  { id: "sedentary", label: "Mostly sitting" },
  { id: "light", label: "Light (1–3 workouts/wk)" },
  { id: "moderate", label: "Moderate (3–5/wk)" },
  { id: "active", label: "Active (6–7/wk)" },
  { id: "very_active", label: "Athlete / physical job" },
] as const;

type Answers = {
  dietary_pattern: (typeof DIETS)[number]["id"];
  avoid_allergens: string[];
  avoid_pork: boolean;
  avoid_alcohol: boolean;
  goal: (typeof GOALS)[number]["id"];
  sex: "male" | "female" | null;
  feet: string;
  inches: string;
  pounds: string;
  age: string;
  activity_level: (typeof ACTIVITY)[number]["id"] | null;
  taste_note: string;
};

const BLANK: Answers = {
  dietary_pattern: "none",
  avoid_allergens: [],
  avoid_pork: false,
  avoid_alcohol: false,
  goal: "maintain",
  sex: null,
  feet: "",
  inches: "",
  pounds: "",
  age: "",
  activity_level: null,
  taste_note: "",
};

const STEPS = ["Diet", "Allergies", "Goal", "About you", "Tastes"] as const;

export default function OnboardingWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Answers>(BLANK);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Prefill when the user is editing an existing profile.
  useEffect(() => {
    fetch("/api/profile").then(async (resp) => {
      if (resp.status === 401) {
        router.push("/login");
        return;
      }
      const p = await resp.json();
      if (!p.exists) return;
      const totalInches = p.height_cm ? p.height_cm / 2.54 : null;
      setAnswers({
        dietary_pattern: p.dietary_pattern,
        avoid_allergens: p.avoid_allergens,
        avoid_pork: p.avoid_pork,
        avoid_alcohol: p.avoid_alcohol,
        goal: p.goal,
        sex: p.sex,
        feet: totalInches ? String(Math.floor(totalInches / 12)) : "",
        inches: totalInches ? String(Math.round(totalInches % 12)) : "",
        pounds: p.weight_kg ? String(Math.round(p.weight_kg * 2.20462)) : "",
        age: p.age_years ? String(p.age_years) : "",
        activity_level: p.activity_level,
        taste_note: p.taste_note ?? "",
      });
    });
  }, [router]);

  const set = <K extends keyof Answers>(key: K, value: Answers[K]) =>
    setAnswers((a) => ({ ...a, [key]: value }));

  const bodyStarted =
    answers.sex !== null || answers.age !== "" || answers.feet !== "" ||
    answers.pounds !== "" || answers.activity_level !== null;
  const bodyComplete =
    answers.sex !== null && answers.age !== "" && answers.feet !== "" &&
    answers.pounds !== "" && answers.activity_level !== null;

  async function save() {
    setBusy(true);
    setError(null);
    const body = {
      dietary_pattern: answers.dietary_pattern,
      avoid_allergens: answers.avoid_allergens,
      avoid_pork: answers.avoid_pork,
      avoid_alcohol: answers.avoid_alcohol,
      goal: answers.goal,
      sex: bodyComplete ? answers.sex : null,
      age_years: bodyComplete ? Number(answers.age) : null,
      height_cm: bodyComplete
        ? Math.round((Number(answers.feet) * 12 + Number(answers.inches || 0)) * 2.54 * 10) / 10
        : null,
      weight_kg: bodyComplete
        ? Math.round((Number(answers.pounds) / 2.20462) * 10) / 10
        : null,
      activity_level: bodyComplete ? answers.activity_level : null,
      taste_note: answers.taste_note || null,
    };
    const resp = await fetch("/api/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (resp.ok) {
      router.push("/");
      return;
    }
    const detail = (await resp.json().catch(() => null))?.detail;
    setError(typeof detail === "string" ? detail : "Could not save. Check your answers.");
    setBusy(false);
  }

  const card = (selected: boolean) =>
    `w-full rounded-xl border-2 p-4 text-left transition-colors ${
      selected
        ? "border-red-700 bg-red-50"
        : "border-zinc-200 bg-white hover:border-zinc-400"
    }`;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-xl flex-col gap-6 px-4 py-10">
      {/* progress */}
      <div className="flex items-center gap-2">
        {STEPS.map((name, i) => (
          <div key={name} className="flex flex-1 flex-col gap-1">
            <div className={`h-1.5 rounded-full ${i <= step ? "bg-red-700" : "bg-zinc-200"}`} />
            <span className={`text-xs ${i === step ? "font-semibold text-zinc-900" : "text-zinc-400"}`}>
              {name}
            </span>
          </div>
        ))}
      </div>

      {step === 0 && (
        <section className="flex flex-col gap-3">
          <h1 className="text-2xl font-bold text-zinc-900">How do you eat?</h1>
          {DIETS.map((d) => (
            <button key={d.id} onClick={() => set("dietary_pattern", d.id)} className={card(answers.dietary_pattern === d.id)}>
              <span className="font-semibold text-zinc-900">{d.label}</span>
              <span className="block text-sm text-zinc-500">{d.hint}</span>
            </button>
          ))}
          <div className="mt-2 flex flex-col gap-2">
            <label className="flex items-center gap-3 text-zinc-800">
              <input type="checkbox" checked={answers.avoid_pork} onChange={(e) => set("avoid_pork", e.target.checked)} className="h-5 w-5 accent-red-700" />
              I avoid pork
            </label>
            <label className="flex items-center gap-3 text-zinc-800">
              <input type="checkbox" checked={answers.avoid_alcohol} onChange={(e) => set("avoid_alcohol", e.target.checked)} className="h-5 w-5 accent-red-700" />
              I avoid dishes cooked with alcohol
            </label>
          </div>
        </section>
      )}

      {step === 1 && (
        <section className="flex flex-col gap-3">
          <h1 className="text-2xl font-bold text-zinc-900">Any allergies?</h1>
          <p className="text-sm text-zinc-500">
            Meals containing these are never recommended to you. Skip if none.
          </p>
          <div className="flex flex-wrap gap-2">
            {ALLERGENS.map((a) => {
              const on = answers.avoid_allergens.includes(a);
              return (
                <button
                  key={a}
                  onClick={() =>
                    set(
                      "avoid_allergens",
                      on ? answers.avoid_allergens.filter((x) => x !== a) : [...answers.avoid_allergens, a],
                    )
                  }
                  className={`rounded-full border-2 px-4 py-2 text-sm font-medium capitalize transition-colors ${
                    on ? "border-red-700 bg-red-700 text-white" : "border-zinc-300 bg-white text-zinc-700 hover:border-zinc-500"
                  }`}
                >
                  {a}
                </button>
              );
            })}
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="flex flex-col gap-3">
          <h1 className="text-2xl font-bold text-zinc-900">What&apos;s your goal?</h1>
          {GOALS.map((g) => (
            <button key={g.id} onClick={() => set("goal", g.id)} className={card(answers.goal === g.id)}>
              <span className="font-semibold text-zinc-900">{g.label}</span>
              <span className="block text-sm text-zinc-500">{g.hint}</span>
            </button>
          ))}
        </section>
      )}

      {step === 3 && (
        <section className="flex flex-col gap-4">
          <h1 className="text-2xl font-bold text-zinc-900">About you <span className="text-base font-normal text-zinc-400">(optional)</span></h1>
          <p className="text-sm text-zinc-500">
            With this we compute a daily calorie target for smarter portions.
            Leave it all blank to skip.
          </p>
          <div className="flex gap-3">
            {(["male", "female"] as const).map((s) => (
              <button key={s} onClick={() => set("sex", answers.sex === s ? null : s)} className={card(answers.sex === s) + " capitalize"}>
                {s}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-sm font-medium text-zinc-700">
              Age
              <input type="number" min={13} max={100} value={answers.age} onChange={(e) => set("age", e.target.value)}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-base" placeholder="19" />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium text-zinc-700">
              Weight (lbs)
              <input type="number" min={66} max={660} value={answers.pounds} onChange={(e) => set("pounds", e.target.value)}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-base" placeholder="160" />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium text-zinc-700">
              Height (ft)
              <input type="number" min={3} max={8} value={answers.feet} onChange={(e) => set("feet", e.target.value)}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-base" placeholder="5" />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium text-zinc-700">
              Height (in)
              <input type="number" min={0} max={11} value={answers.inches} onChange={(e) => set("inches", e.target.value)}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-base" placeholder="10" />
            </label>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium text-zinc-700">Activity level</span>
            {ACTIVITY.map((a) => (
              <button key={a.id} onClick={() => set("activity_level", answers.activity_level === a.id ? null : a.id)} className={card(answers.activity_level === a.id)}>
                {a.label}
              </button>
            ))}
          </div>
          {bodyStarted && !bodyComplete && (
            <p className="text-sm text-amber-700">
              Fill in all of these (or clear them all) before continuing.
            </p>
          )}
        </section>
      )}

      {step === 4 && (
        <section className="flex flex-col gap-3">
          <h1 className="text-2xl font-bold text-zinc-900">What do you love eating? <span className="text-base font-normal text-zinc-400">(optional)</span></h1>
          <p className="text-sm text-zinc-500">
            A sentence or two. We use this to nudge similar meals up your list.
          </p>
          <textarea
            value={answers.taste_note}
            onChange={(e) => set("taste_note", e.target.value)}
            maxLength={500}
            rows={4}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-base"
            placeholder="e.g. Big fan of spicy Korean food and grilled chicken. Not into mushrooms or super sweet breakfasts."
          />
        </section>
      )}

      {error && <p className="text-sm text-red-700">{error}</p>}

      <div className="mt-auto flex gap-3 pt-4">
        {step > 0 && (
          <button onClick={() => setStep(step - 1)} className="rounded-lg border border-zinc-300 px-5 py-2.5 font-semibold text-zinc-700 hover:bg-zinc-100">
            Back
          </button>
        )}
        {step < STEPS.length - 1 ? (
          <button
            onClick={() => setStep(step + 1)}
            disabled={step === 3 && bodyStarted && !bodyComplete}
            className="ml-auto rounded-lg bg-red-700 px-6 py-2.5 font-semibold text-white hover:bg-red-800 disabled:opacity-40"
          >
            Next
          </button>
        ) : (
          <button onClick={save} disabled={busy} className="ml-auto rounded-lg bg-red-700 px-6 py-2.5 font-semibold text-white hover:bg-red-800 disabled:opacity-50">
            {busy ? "Saving…" : "Save my preferences"}
          </button>
        )}
      </div>
    </main>
  );
}
