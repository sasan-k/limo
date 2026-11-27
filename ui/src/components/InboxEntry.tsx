import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { postJson } from "@/api/client";
import type { InboxItem } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** Continue for one item: escalations need a typed response, budget holds do not. */
function ContinueForm({ item }: { item: InboxItem }) {
  const queryClient = useQueryClient();
  const [response, setResponse] = useState("");
  const needsResponse = item.kind === "escalation";
  const send = useMutation({
    mutationFn: () =>
      postJson(`/api/inbox/${encodeURIComponent(item.id)}/continue`, needsResponse ? { response } : {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["inbox"] });
      void queryClient.invalidateQueries({ queryKey: ["board"] });
    },
  });
  return (
    <>
      {needsResponse && (
        <label className="flex flex-col gap-1">
          Response
          <textarea
            className="rounded-md border border-border bg-background p-2"
            value={response}
            maxLength={2000}
            onChange={(e) => setResponse(e.target.value)}
          />
        </label>
      )}
      <div className="flex items-center gap-3">
        <Button
          size="sm"
          disabled={send.isPending || (needsResponse && response.trim() === "")}
          onClick={() => send.mutate()}
        >
          Continue
        </Button>
        {send.isError && <span className="text-destructive">{send.error.message}</span>}
      </div>
    </>
  );
}

/** One inbox item: ticket, ask, issue link, and Continue (REQ-41). */
export function InboxEntry({ item }: { item: InboxItem }) {
  return (
    <Card data-testid={`inbox-${item.ticket}`}>
      <CardHeader>
        <div className="flex flex-col gap-1">
          <CardTitle>{item.ticket}</CardTitle>
          <CardDescription>
            {item.project} / {item.feature}
          </CardDescription>
        </div>
        <Badge variant={item.kind === "escalation" ? "destructive" : "secondary"}>{item.kind}</Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <p>{item.reason}</p>
        {item.link && (
          <a
            className="text-foreground underline decoration-primary decoration-2"
            href={item.link}
            target="_blank"
            rel="noreferrer"
          >
            Open issue
          </a>
        )}
        <ContinueForm item={item} />
      </CardContent>
    </Card>
  );
}
