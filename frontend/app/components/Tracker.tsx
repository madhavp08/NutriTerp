"use client";

import { useEffect, useState } from "react";

export type LogEntry = {
  id: number;
  meal: string;
  name: string;
  calories: number | null;
  protein_g: number | null;
  hall: string | null;
  has_photo: boolean;
};

export type DayLog = {
  date: string;
  calorie_target: number | null;
  calories_eaten: number;
  remaining: number | null;
  entries: LogEntry[];
};

const MEALS = ["breakfast", "lunch", "dinner", "snack"] as const;

export default function Tracker({
  onChange,
}: {
  onChange: () => void;
}) {
  const [day, setDay] = useState<DayLog | null>(null);
  const [name, setName] = useState("");
  const [calories, setCalories] = useState("");
  const [meal, setMeal] = useState<(typeof MEALS)[number]>("lunch");
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    const resp = await fetch("/api/logs");
    if (resp.ok) setDay(await resp.json());
  }

  useEffect(() => {
    reload();
  }, []);

  async function addEntry(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      let resp: Response;
      if (photo) {
        const form = new FormData();
        form.set("meal", meal);
        form.set("name", name.trim() || "Meal photo");
        if (calories) form.set("calories", calories);
        form.set("photo", photo);
        resp = await fetch("/api/logs/photo", { method: "POST", body: form });
      } else {
        resp = await fetch("/api/logs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            meal,
            name: name.trim(),
            calories: calories ? Number(calories) : null,
          }),
        });
      }
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || "Could not save that meal.");
      }
      setDay(await resp.json());
      setName("");
      setCalories("");
      setPhoto(null);
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save that meal.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    const resp = await fetch(`/api/logs/${id}`, { method: "DELETE" });
    if (resp.ok) {
      setDay(await resp.json());
      onChange();
    }
  }

  const eaten = day?.calories_eaten ?? 0;
  const target = day?.calorie_target;
  const pct = target ? Math.min(100, Math.round((eaten / target) * 100)) : 0;

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-bold text-zinc-900">Today&apos;s log</h3>
      <p className="mt-1 text-sm text-zinc-500">
        {target
          ? `${Math.round(eaten)} / ${target} kcal`
          : `${Math.round(eaten)} kcal logged`}
        {day?.remaining != null && (
          <span>
            {" "}
            · {day.remaining >= 0 ? `${Math.round(day.remaining)} left` : `${Math.round(-day.remaining)} over`}
          </span>
        )}
      </p>
      {target != null && (
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-100">
          <div
            className={`h-full rounded-full ${pct > 100 ? "bg-red-600" : "bg-red-700"}`}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        </div>
      )}

      <ul className="mt-4 flex flex-col gap-2">
        {day?.entries.length === 0 && (
          <li className="text-sm text-zinc-400">Nothing logged yet.</li>
        )}
        {day?.entries.map((entry) => (
          <li key={entry.id} className="flex items-center justify-between gap-3 text-sm">
            <div>
              <span className="font-medium text-zinc-800">{entry.name}</span>
              <span className="ml-2 text-zinc-400">
                {entry.meal}
                {entry.calories != null ? ` · ${Math.round(entry.calories)} kcal` : ""}
                {entry.has_photo ? " · photo" : ""}
              </span>
            </div>
            <button
              type="button"
              onClick={() => remove(entry.id)}
              className="text-xs font-medium text-zinc-400 hover:text-red-700"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>

      <form onSubmit={addEntry} className="mt-4 flex flex-col gap-2 border-t border-zinc-100 pt-4">
        <div className="flex flex-wrap gap-2">
          <select
            value={meal}
            onChange={(e) => setMeal(e.target.value as (typeof MEALS)[number])}
            className="rounded-lg border border-zinc-300 bg-white px-2 py-2 text-sm"
          >
            {MEALS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="What did you eat?"
            className="min-w-40 flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm"
          />
          <input
            value={calories}
            onChange={(e) => setCalories(e.target.value)}
            type="number"
            min={0}
            placeholder="kcal"
            className="w-24 rounded-lg border border-zinc-300 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="cursor-pointer text-sm font-medium text-red-700 hover:underline">
            {photo ? photo.name : "Add a meal photo"}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
            />
          </label>
          <button
            type="submit"
            disabled={busy || (!name.trim() && !photo)}
            className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800 disabled:opacity-50"
          >
            {busy ? "Saving…" : "Log meal"}
          </button>
        </div>
        {error && <p className="text-sm text-red-700">{error}</p>}
      </form>
    </section>
  );
}

export async function logSuggestion(meal: {
  menu_item_id: number;
  name: string;
  hall_id: number;
  meal: string;
  calories: number | null;
  protein_g: number | null;
}): Promise<DayLog> {
  const resp = await fetch("/api/logs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      meal: meal.meal,
      hall_id: meal.hall_id,
      menu_item_id: meal.menu_item_id,
      name: meal.name,
      calories: meal.calories,
      protein_g: meal.protein_g,
    }),
  });
  if (!resp.ok) throw new Error("Could not log that meal.");
  return resp.json();
}
