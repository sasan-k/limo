import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useEffect } from "react";

/** SSE event type → REST queries it invalidates (api.md › SSE events; REST stays the truth). */
export const INVALIDATES: Record<string, QueryKey[]> = {
  "run.started": [["agent-cards"]],
  "run.updated": [["agent-cards"]],
  "run.finished": [["agent-cards"], ["board"], ["inbox"], ["costs"]],
  "incident.opened": [["agent-cards"], ["board"], ["inbox"]],
  "cost.updated": [["agent-cards"], ["costs"]],
  "ticket.changed": [["board"]],
  "prompt.saved": [["prompt"], ["prompt-history"]],
};

/** Opens one EventSource on /api/events and refetches the matching queries on each event. */
export function useLiveEvents(): void {
  const queryClient = useQueryClient();
  useEffect(() => {
    const source = new EventSource("/api/events");
    for (const [type, keys] of Object.entries(INVALIDATES)) {
      source.addEventListener(type, () => {
        for (const queryKey of keys) void queryClient.invalidateQueries({ queryKey });
      });
    }
    return () => source.close();
  }, [queryClient]);
}
