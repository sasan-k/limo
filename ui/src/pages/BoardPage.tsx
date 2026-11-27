import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getJson } from "@/api/client";
import type { Board, Project } from "@/api/types";
import { TicketCard } from "@/components/TicketCard";

function FeatureBoard({ board }: { board: Board }) {
  return (
    <>
      {board.features.map((feature) => (
        <section key={feature.name} aria-label={`feature ${feature.name}`} className="flex flex-col gap-3">
          <h2 className="font-semibold">{feature.name}</h2>
          <div className="grid auto-cols-[minmax(12rem,1fr)] grid-flow-col gap-3 overflow-x-auto">
            {board.statuses.map((status) => (
              <section
                key={status}
                aria-label={`${feature.name} ${status}`}
                className="flex flex-col gap-2 rounded-lg bg-muted p-2"
              >
                <h3 className="text-muted-foreground text-xs font-medium uppercase">{status}</h3>
                {feature.tickets
                  .filter((t) => t.status === status)
                  .map((ticket) => (
                    <TicketCard key={ticket.id} ticket={ticket} />
                  ))}
              </section>
            ))}
          </div>
        </section>
      ))}
    </>
  );
}

/** Tickets of every feature of one project, in one column per ticket status (REQ-40). */
export function BoardPage() {
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => getJson<Project[]>("/api/projects") });
  const [chosen, setChosen] = useState<string | null>(null);
  const project = chosen ?? projects.data?.[0]?.name ?? null;
  const board = useQuery({
    queryKey: ["board", project],
    queryFn: () => getJson<Board>(`/api/projects/${encodeURIComponent(project ?? "")}/board`),
    enabled: project !== null,
  });
  if (projects.isPending) return <p className="text-muted-foreground">Loading projects…</p>;
  if (projects.isError) return <p className="text-destructive">Could not load projects.</p>;
  if (project === null) return <p className="text-muted-foreground">No projects yet.</p>;
  return (
    <div className="flex flex-col gap-4">
      <label className="flex items-center gap-2 text-sm">
        Project
        <select
          className="rounded-md border border-border bg-background px-2 py-1"
          value={project}
          onChange={(e) => setChosen(e.target.value)}
        >
          {projects.data.map((p) => (
            <option key={p.name}>{p.name}</option>
          ))}
        </select>
      </label>
      {board.isError && <p className="text-destructive">{board.error.message}</p>}
      {board.data && <FeatureBoard board={board.data} />}
    </div>
  );
}
