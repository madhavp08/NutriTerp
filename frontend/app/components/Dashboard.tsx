"use client";

import { useEffect, useState } from "react";

/** One suggested meal as returned by GET /api/suggestions. */
type Meal = {
  menu_item_id: number;
  name: string;
  hall: string;
  station: string;
  calories: number | null;
  protein_g: number | null;
  diet_flags: string[];
  reasons: string[];
  liked: boolean | null;
};

type Suggestions = {
  date: string;
  meal_budget: number;
  calorie_target: number | null;
  meals: { breakfast: Meal | null; lunch: Meal | null; dinner: Meal | null };
};

const MEAL_LABELS = { breakfast: "Breakfast", lunch: "Lunch", dinner: "Dinner" } as const;

export default function Dashboard() {
  const [data, setData] = useState<Suggestions | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/suggestions").then(async (resp) => {
      if (resp.ok) setData(await resp.json());
      else setError("Could not load today's suggestions.");
    });
  }, []);

  async function rate(meal: Meal, liked: boolean) {
    // Optimistic: flip the button immediately, then persist.
    setData((d) => {
      if (!d) return d;
      const meals = { ...d.meals };
      for (const key of Object.keys(meals) as (keyof typeof meals)[]) {
        if (meals[key]?.menu_item_id === meal.menu_item_id) {
          meals[key] = { ...meals[key]!, liked };
        }
      }
      return { ...d, meals };
    });
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ menu_item_id: meal.menu_item_id, liked }),
    });
  }

  if (error) return <p className="text-red-700">{error}</p>;
  if (!data) return <p className="text-zinc-400">Picking your meals…</p>;

  const dateLabel = new Date(data.date + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric",
  });

  return (
    <div className="flex w-full flex-col gap-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-bold text-zinc-900">Today, {dateLabel}</h2>
        <p className="text-sm text-zinc-500">
          {data.calorie_target
            ? `Daily target ${data.calorie_target} kcal · ~${data.meal_budget} per meal`
            : `Planning ~${data.meal_budget} kcal per meal`}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {(Object.keys(MEAL_LABELS) as (keyof typeof MEAL_LABELS)[]).map((key) => {
          const meal = data.meals[key];
          return (
            <div key={key} className="flex flex-col rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-red-700">
                {MEAL_LABELS[key]}
              </span>
              {meal ? (
                <>
                  <h3 className="mt-1 text-lg font-bold leading-snug text-zinc-900">{meal.name}</h3>
                  <p className="mt-0.5 text-sm text-zinc-500">
                    {meal.hall} · {meal.station}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {meal.calories != null && (
                      <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700">
                        {Math.round(meal.calories)} kcal
                      </span>
                    )}
                    {meal.protein_g != null && (
                      <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700">
                        {Math.round(meal.protein_g)}g protein
                      </span>
                    )}
                    {meal.diet_flags.filter((f) => ["vegan", "vegetarian", "halal_friendly"].includes(f)).map((f) => (
                      <span key={f} className="rounded-full bg-green-100 px-2.5 py-1 text-xs font-medium text-green-800">
                        {f.replace("_", " ")}
                      </span>
                    ))}
                  </div>
                  {meal.reasons.length > 0 && (
                    <p className="mt-3 text-sm text-zinc-600">{meal.reasons.join(" · ")}</p>
                  )}
                  <div className="mt-auto flex gap-2 pt-4">
                    <button
                      onClick={() => rate(meal, true)}
                      aria-label={`Like ${meal.name}`}
                      className={`flex-1 rounded-lg border px-3 py-2 text-sm font-semibold transition-colors ${
                        meal.liked === true
                          ? "border-green-600 bg-green-600 text-white"
                          : "border-zinc-300 text-zinc-700 hover:border-green-600 hover:text-green-700"
                      }`}
                    >
                      Like
                    </button>
                    <button
                      onClick={() => rate(meal, false)}
                      aria-label={`Dislike ${meal.name}`}
                      className={`flex-1 rounded-lg border px-3 py-2 text-sm font-semibold transition-colors ${
                        meal.liked === false
                          ? "border-red-600 bg-red-600 text-white"
                          : "border-zinc-300 text-zinc-700 hover:border-red-600 hover:text-red-700"
                      }`}
                    >
                      Dislike
                    </button>
                  </div>
                </>
              ) : (
                <p className="mt-2 text-sm text-zinc-400">
                  No {MEAL_LABELS[key].toLowerCase()} on today&apos;s menu that fits
                  your preferences.
                </p>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-xs text-zinc-400">
        Your Like / Dislike votes train the recommender — the more you rate,
        the better tomorrow&apos;s picks get.
      </p>
    </div>
  );
}
