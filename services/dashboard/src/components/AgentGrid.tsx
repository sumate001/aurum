"use client";

interface AgentOutput {
  agent_name: string;
  signal: string;
  value: number;
  metadata: Record<string, unknown>;
}

export default function AgentGrid({ agents }: { agents: AgentOutput[] }) {
  if (!agents || agents.length === 0) return null;

  const signalColor: Record<string, string> = {
    BUY: "bg-green-900 border-green-600 text-green-300",
    SELL: "bg-red-900 border-red-600 text-red-300",
    HOLD: "bg-gray-800 border-gray-600 text-gray-400",
  };

  return (
    <div className="rounded-xl border border-gray-700 p-4 bg-gray-900">
      <div className="text-xs text-gray-500 mb-3">Technical Agents</div>
      <div className="grid grid-cols-2 gap-2">
        {agents.map((ag) => (
          <div
            key={ag.agent_name}
            className={`rounded-lg border px-3 py-2 text-sm ${signalColor[ag.signal] || signalColor.HOLD}`}
          >
            <div className="font-medium">{ag.agent_name}</div>
            <div className="text-xs mt-0.5">{ag.signal} · {ag.value?.toFixed(2)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
