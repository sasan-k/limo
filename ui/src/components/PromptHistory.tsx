import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getJson, postJson } from "@/api/client";
import { fileUrl } from "@/api/prompts";
import type { PromptFile, PromptVersion } from "@/api/types";
import { Button } from "@/components/ui/button";
import { formatTime } from "@/lib/format";

function VersionItem(props: { v: PromptVersion; current: boolean; busy: boolean; onRollback: () => void }) {
  const short = props.v.version.slice(0, 7);
  return (
    <li className="flex flex-col gap-1">
      <span className="font-mono">{short}</span>
      <span className="text-muted-foreground">
        {formatTime(props.v.saved_at)} · {props.v.message}
      </span>
      {!props.current && (
        <Button variant="outline" size="sm" disabled={props.busy} onClick={props.onRollback}>
          Roll back to {short}
        </Button>
      )}
    </li>
  );
}

/** Versions of one file, newest first; Roll back restores one as a new version (REQ-43). */
export function PromptHistory({ agent, path }: { agent: string; path: string }) {
  const queryClient = useQueryClient();
  const history = useQuery({
    queryKey: ["prompt-history", agent, path],
    queryFn: () => getJson<PromptVersion[]>(fileUrl(agent, path, "history")),
  });
  const rollback = useMutation({
    mutationFn: (version: string) => postJson<PromptFile>(fileUrl(agent, path, "rollback"), { version }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["prompt"] });
      void queryClient.invalidateQueries({ queryKey: ["prompt-history"] });
    },
  });
  if (history.isPending) return <p className="text-muted-foreground text-sm">Loading history…</p>;
  if (history.isError) return <p className="text-destructive text-sm">{history.error.message}</p>;
  return (
    <section aria-label="history" className="flex flex-col gap-2 text-sm">
      <h2 className="font-semibold">History</h2>
      {rollback.isError && <p className="text-destructive">{rollback.error.message}</p>}
      <ol className="flex flex-col gap-2">
        {history.data.map((v, i) => (
          <VersionItem
            key={v.version}
            v={v}
            current={i === 0}
            busy={rollback.isPending}
            onRollback={() => rollback.mutate(v.version)}
          />
        ))}
      </ol>
    </section>
  );
}
