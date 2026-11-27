import type { AgentCard as AgentCardData } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDuration, formatTime, formatTokens, formatUsd } from "@/lib/format";

const STATE_VARIANT = { idle: "secondary", active: "default", stuck: "destructive" } as const;

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd data-field={label}>{value}</dd>
    </div>
  );
}

/** One agent: model, state, current ticket, its cost on that ticket, and its last run (REQ-39). */
export function AgentCard({ card }: { card: AgentCardData }) {
  const run = card.last_run;
  return (
    <Card data-testid={`agent-card-${card.agent}`} aria-label={`agent ${card.agent}`}>
      <CardHeader>
        <div className="flex flex-col gap-1">
          <CardTitle>{card.agent}</CardTitle>
          <CardDescription>{card.model}</CardDescription>
        </div>
        <Badge variant={STATE_VARIANT[card.state]} data-field="state">
          {card.state}
        </Badge>
      </CardHeader>
      <CardContent>
        <dl className="flex flex-col gap-1">
          <Field label="ticket" value={card.ticket ?? "—"} />
          <Field label="cost" value={formatUsd(card.cost)} />
          <Field label="last run" value={run ? formatTokens(run.tokens) : "—"} />
          <Field label="duration" value={run ? formatDuration(run.duration_s) : "—"} />
          <Field label="finished" value={run ? formatTime(run.finished_at) : "—"} />
          <Field label="tries" value={run ? String(run.tries) : "—"} />
        </dl>
      </CardContent>
    </Card>
  );
}
