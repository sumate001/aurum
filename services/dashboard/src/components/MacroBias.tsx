"use client";

interface Props {
  direction: string;
  confidence: number;
  reasoning: string;
}

export default function MacroBias({ direction, confidence, reasoning }: Props) {
  const color =
    direction === "BULLISH"
      ? "text-green-400"
      : direction === "BEARISH"
      ? "text-red-400"
      : "text-gray-400";

  return (
    <div className="rounded-xl border border-gray-700 p-4 bg-gray-900">
      <div className="text-xs text-gray-500 mb-1">Macro Bias (MiroFish)</div>
      <div className={`text-2xl font-bold ${color}`}>{direction}</div>
      <div className="text-sm text-gray-400 mt-1">Confidence: {confidence}%</div>
      <div className="text-xs text-gray-500 mt-2 line-clamp-3">{reasoning}</div>
    </div>
  );
}
