import { useQuery } from "@tanstack/react-query";

import { getJson } from "@/api/client";
import { useChosenProject } from "@/api/projects";
import type { CostTotals } from "@/api/types";
import { CostTable } from "@/components/CostTable";
import { Select } from "@/components/Select";
import { formatUsd } from "@/lib/format";

function Totals({ costs }: { costs: CostTotals }) {
  return (
    <div className="flex flex-col gap-6">
      <p className="text-lg">
        Overall <span data-testid="cost-overall">{formatUsd(costs.overall)}</span>
      </p>
      <div className="grid gap-6 md:grid-cols-3">
        <CostTable title="Per agent" rows={Object.entries(costs.per_agent)} />
        <CostTable title="Per ticket" rows={Object.entries(costs.per_ticket)} />
        <CostTable
          title="Per agent on ticket"
          rows={costs.per_agent_ticket.map((c) => [`${c.agent} on ${c.ticket}`, c.cost])}
        />
      </div>
    </div>
  );
}

/** The four cost totals of one project: per agent, per ticket, per agent on ticket, overall (REQ-44). */
export function CostPage() {
  const { projects, names, project, setProject } = useChosenProject();
  const costs = useQuery({
    queryKey: ["costs", project],
    queryFn: () => getJson<CostTotals>(`/api/projects/${encodeURIComponent(project ?? "")}/costs`),
    enabled: project !== null,
  });
  if (projects.isPending) return <p className="text-muted-foreground">Loading projects…</p>;
  if (projects.isError) return <p className="text-destructive">Could not load projects.</p>;
  if (project === null) return <p className="text-muted-foreground">No projects yet.</p>;
  return (
    <div className="flex flex-col gap-4">
      <Select label="Project" value={project} options={names} onChange={setProject} />
      {costs.isError && <p className="text-destructive">{costs.error.message}</p>}
      {costs.data && <Totals costs={costs.data} />}
    </div>
  );
}
