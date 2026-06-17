"use client";

interface Signal {
  id: string;
  action: string;
  symbol: string;
  timeframe: string;
  entry: number;
  sl: number;
  tp1: number;
  tp2: number;
  confidence: number;
  macro_bias: string;
  macro_confidence: number;
  technical_consensus: string;
  reasoning: string;
  status: string;
  created_at: string;
}

export default function SignalCard({ signal }: { signal: Signal }) {
  const actionColor =
    signal.action === "BUY"
      ? "text-green-400 border-green-600"
      : signal.action === "SELL"
      ? "text-red-400 border-red-600"
      : "text-gray-400 border-gray-600";

  const statusBadge: Record<string, string> = {
    PENDING_APPROVAL: "bg-yellow-900 text-yellow-300",
    APPROVED: "bg-blue-900 text-blue-300",
    REJECTED: "bg-red-900 text-red-300",
    EXECUTED: "bg-green-900 text-green-300",
    CANCELLED: "bg-gray-800 text-gray-400",
  };

  return (
    <div className={`rounded-xl border p-4 bg-gray-900 ${actionColor} space-y-2`}>
      <div className="flex justify-between items-center">
        <span className={`text-xl font-bold ${actionColor}`}>{signal.action}</span>
        <span className={`text-xs px-2 py-0.5 rounded-full ${statusBadge[signal.status] || "bg-gray-800"}`}>
          {signal.status}
        </span>
      </div>
      <div className="text-sm text-gray-400">
        {signal.symbol} · {signal.timeframe} · {new Date(signal.created_at).toLocaleString()}
      </div>
      <div className="grid grid-cols-3 gap-2 text-sm mt-2">
        <div>
          <div className="text-gray-500 text-xs">Entry</div>
          <div>{signal.entry?.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">SL</div>
          <div className="text-red-400">{signal.sl?.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">TP1</div>
          <div className="text-green-400">{signal.tp1?.toFixed(2)}</div>
        </div>
      </div>
      <div className="flex gap-4 text-sm mt-1">
        <div>
          <span className="text-gray-500">Confidence: </span>
          <span className="font-semibold">{signal.confidence}%</span>
        </div>
        <div>
          <span className="text-gray-500">Macro: </span>
          <span>{signal.macro_bias} ({signal.macro_confidence}%)</span>
        </div>
      </div>
      <div className="text-xs text-gray-500 mt-1">{signal.technical_consensus}</div>
      {signal.reasoning && (
        <div className="text-xs text-gray-400 mt-1 line-clamp-2">{signal.reasoning}</div>
      )}
    </div>
  );
}
