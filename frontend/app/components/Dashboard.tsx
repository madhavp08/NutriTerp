"use client";

import { useEffect, useState } from "react";

import PhotoCalendar from "./PhotoCalendar";
import Tracker, { logSuggestion } from "./Tracker";

type Meal = {
  menu_item_id: number;
  name: string;
  hall_id: number;
  hall: string;
  meal: "breakfast" | "lunch" | "dinner";
  station: string;
  calories: number | null;
  protein_g: number | null;
  diet_flags: string[];
  reasons: string[];
  liked: boolean | null;
};

type HallBlock = {
  hall_id: number;
  name: string;
  meals: { breakfast: Meal | null; lunch: Meal | null; dinner: Meal | null };
};

type Suggestions = {
  date: string;
  meal_budget: number;
  calorie_target: number | null;
  halls: HallBlock[];
};

const MEAL_LABELS = { breakfast: "Breakfast", lunch: "Lunch", dinner: "Dinner" } as const;
const MEAL_KEYS = ["breakfast", "lunch", "dinner"] as const;

export default function Dashboard() {
  const [data, setData] = useState<Suggestions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logTick, setLogTick] = useState(0);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/suggestions").then(async (resp) => {
      if (resp.ok) setData(await resp.json());
      else setError("Could not load today's suggestions.");
    });
  }, []);

  function replaceSlot(hallId: number, meal: Meal["meal"], next: Meal | null) {
    setData((d) => {
      if (!d) return d;
      return {
        ...d,
        halls: d.halls.map((hall) =>
          hall.hall_id !== hallId
            ? hall
            : { ...hall, meals: { ...hall.meals, [meal]: next } },
        ),
      };
    });
  }

  async function rate(card: Meal, liked: boolean) {
    const resp = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        menu_item_id: card.menu_item_id,
        liked,
        hall_id: card.hall_id,
        meal: card.meal,
      }),
    });
    const body = await resp.json();
    if (!liked && body.replacement) {
      replaceSlot(card.hall_id, card.meal, body.replacement);
    } else if (!liked) {
      replaceSlot(card.hall_id, card.meal, null);
    } else {
      replaceSlot(card.hall_id, card.meal, { ...card, liked: true });
    }
  }

  async function ateThis(card: Meal) {
    try {
      await logSuggestion(card);
      setLogTick((n) => n + 1);
      setToast(`Logged ${card.name}`);
      setTimeout(() => setToast(null), 2000);
    } catch {
      setToast("Could not log that meal.");
    }
  }

  if (error) return <p className="text-red-700">{error}</p>;
  if (!data) return <p className="text-zinc-400">Picking your meals…</p>;

  const dateLabel = new Date(data.date + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="flex w-full flex-col gap-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-bold text-zinc-900">Today, {dateLabel}</h2>
        <p className="text-sm text-zinc-500">
          {data.calorie_target
            ? `Daily target ${data.calorie_target} kcal · ~${data.meal_budget} per meal`
            : `Planning ~${data.meal_budget} kcal per meal`}
        </p>
      </div>

      <div className="overflow-x-auto">
        <div className="grid min-w-[720px] grid-cols-[5.5rem_repeat(3,minmax(0,1fr))] gap-3">
          <div />
          {data.halls.map((hall) => (
            <div key={hall.hall_id} className="px-1 text-sm font-semibold text-zinc-800">
              {hall.name}
            </div>
          ))}
          {MEAL_KEYS.map((mealKey) => (
            <div key={mealKey} className="contents">
              <div className="flex items-center text-xs font-semibold uppercase tracking-wider text-red-700">
                {MEAL_LABELS[mealKey]}
              </div>
              {data.halls.map((hall) => {
                const card = hall.meals[mealKey];
                return (
                  <MealCard
                    key={`${hall.hall_id}-${mealKey}`}
                    card={card}
                    onLike={() => card && rate(card, true)}
                    onDislike={() => card && rate(card, false)}
                    onLog={() => card && ateThis(card)}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-zinc-400">
        Dislike swaps only that hall and meal — the other eight picks stay put.
        Like / Dislike also trains the ranker.
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        <Tracker key={logTick} onChange={() => setLogTick((n) => n + 1)} />
        <PhotoCalendar refreshKey={logTick} />
      </div>
      {toast && (
        <p className="fixed bottom-4 right-4 rounded-lg bg-zinc-900 px-4 py-2 text-sm text-white shadow-lg">
          {toast}
        </p>
      )}
    </div>
  );
}

function MealCard({
  card,
  onLike,
  onDislike,
  onLog,
}: {
  card: Meal | null;
  onLike: () => void;
  onDislike: () => void;
  onLog: () => void;
}) {
  if (!card) {
    return (
      <div className="rounded-2xl border border-dashed border-zinc-200 bg-white p-4 text-sm text-zinc-400">
        Nothing on this menu fits your filters.
      </div>
    );
  }
  return (
    <div className="flex flex-col rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-bold leading-snug text-zinc-900">{card.name}</h3>
      <p className="mt-0.5 text-xs text-zinc-500">{card.station}</p>
      <div className="mt-2 flex flex-wrap gap-1">
        {card.calories != null && (
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-700">
            {Math.round(card.calories)} kcal
          </span>
        )}
        {card.protein_g != null && (
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-700">
            {Math.round(card.protein_g)}g protein
          </span>
        )}
        {card.diet_flags
          .filter((f) => ["vegan", "vegetarian", "halal_friendly"].includes(f))
          .map((f) => (
            <span key={f} className="rounded-full bg-green-100 px-2 py-0.5 text-[11px] font-medium text-green-800">
              {f.replace("_", " ")}
            </span>
          ))}
      </div>
      {card.reasons.length > 0 && (
        <p className="mt-2 line-clamp-2 text-xs text-zinc-500">{card.reasons.join(" · ")}</p>
      )}
      <div className="mt-auto flex flex-col gap-1.5 pt-3">
        <div className="flex gap-1.5">
          <button
            onClick={onLike}
            aria-label={`Like ${card.name}`}
            className={`flex-1 rounded-lg border px-2 py-1.5 text-xs font-semibold ${
              card.liked === true
                ? "border-green-600 bg-green-600 text-white"
                : "border-zinc-300 text-zinc-700 hover:border-green-600"
            }`}
          >
            Like
          </button>
          <button
            onClick={onDislike}
            aria-label={`Dislike ${card.name}`}
            className={`flex-1 rounded-lg border px-2 py-1.5 text-xs font-semibold ${
              card.liked === false
                ? "border-red-600 bg-red-600 text-white"
                : "border-zinc-300 text-zinc-700 hover:border-red-600"
            }`}
          >
            Dislike
          </button>
        </div>
        <button
          onClick={onLog}
          className="rounded-lg border border-zinc-200 px-2 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50"
        >
          I ate this
        </button>
      </div>
    </div>
  );
}
