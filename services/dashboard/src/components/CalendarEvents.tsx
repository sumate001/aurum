"use client";

interface CalendarEvent {
  event_name: string;
  currency: string;
  impact: string;
  event_datetime: string;
  actual?: string;
  forecast?: string;
  previous?: string;
}

export default function CalendarEvents({ events }: { events: CalendarEvent[] }) {
  if (!events || events.length === 0) {
    return (
      <div className="rounded-xl border border-gray-700 p-4 bg-gray-900">
        <div className="text-xs text-gray-500 mb-2">Economic Calendar</div>
        <div className="text-sm text-gray-600">No upcoming events</div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-700 p-4 bg-gray-900">
      <div className="text-xs text-gray-500 mb-3">Upcoming Events</div>
      <div className="space-y-2">
        {events.map((ev, i) => (
          <div key={i} className="flex justify-between text-sm border-b border-gray-800 pb-2">
            <div>
              <span className="text-yellow-400 text-xs">{ev.currency}</span>
              <span className="ml-2 text-gray-200">{ev.event_name}</span>
            </div>
            <div className="text-gray-500 text-xs">
              {new Date(ev.event_datetime).toLocaleTimeString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
