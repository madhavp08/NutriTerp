"use client";

import { useEffect, useState } from "react";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function monthLabel(year: number, month: number) {
  return new Date(year, month - 1, 1).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });
}

export default function PhotoCalendar({ refreshKey }: { refreshKey: number }) {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [photoDays, setPhotoDays] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetch(`/api/calendar?year=${year}&month=${month}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((body) => {
        if (body) setPhotoDays(new Set(body.photo_days));
      });
  }, [year, month, refreshKey]);

  const first = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const blanks = first.getDay();
  const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

  function shift(delta: number) {
    const next = new Date(year, month - 1 + delta, 1);
    setYear(next.getFullYear());
    setMonth(next.getMonth() + 1);
  }

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-bold text-zinc-900">Photo streak</h3>
        <div className="flex items-center gap-2 text-sm">
          <button
            type="button"
            onClick={() => shift(-1)}
            className="rounded-md px-2 py-1 text-zinc-500 hover:bg-zinc-100"
            aria-label="Previous month"
          >
            ‹
          </button>
          <span className="min-w-36 text-center font-medium text-zinc-700">
            {monthLabel(year, month)}
          </span>
          <button
            type="button"
            onClick={() => shift(1)}
            className="rounded-md px-2 py-1 text-zinc-500 hover:bg-zinc-100"
            aria-label="Next month"
          >
            ›
          </button>
        </div>
      </div>
      <p className="mb-3 text-xs text-zinc-500">
        A green square means you sent a picture of at least one meal that day.
      </p>
      <div className="grid grid-cols-7 gap-1.5 text-center text-[11px] font-medium text-zinc-400">
        {WEEKDAYS.map((d) => (
          <div key={d}>{d}</div>
        ))}
      </div>
      <div className="mt-1 grid grid-cols-7 gap-1.5">
        {Array.from({ length: blanks }, (_, i) => (
          <div key={`b${i}`} />
        ))}
        {Array.from({ length: daysInMonth }, (_, i) => {
          const day = i + 1;
          const key = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const filled = photoDays.has(key);
          const isToday = key === todayKey;
          return (
            <div
              key={key}
              title={filled ? `${key}: meal photo logged` : key}
              className={`flex aspect-square items-center justify-center rounded-md text-xs font-semibold ${
                filled
                  ? "bg-green-500 text-white"
                  : "bg-zinc-100 text-zinc-500"
              } ${isToday ? "ring-2 ring-red-700 ring-offset-1" : ""}`}
            >
              {day}
            </div>
          );
        })}
      </div>
    </section>
  );
}
