import { useQuery } from "@tanstack/react-query";

import { getJson } from "@/api/client";
import type { AgentCard as AgentCardData } from "@/api/types";
import { AgentCard } from "@/components/AgentCard";

/** Grid of live agent cards; SSE events refetch `agent-cards` (see api/events.ts). */
export function AgentsPage() {
  const cards = useQuery({
    queryKey: ["agent-cards"],
    queryFn: () => getJson<AgentCardData[]>("/api/agent-cards"),
  });
  if (cards.isPending) return <p className="text-muted-foreground">Loading agents…</p>;
  if (cards.isError) return <p className="text-destructive">Could not load agents.</p>;
  return (
    <section aria-label="agents" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {cards.data.map((card) => (
        <AgentCard key={card.agent} card={card} />
      ))}
    </section>
  );
}
