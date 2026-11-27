import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { putJson } from "@/api/client";
import { fileUrl } from "@/api/prompts";
import type { PromptFile } from "@/api/types";
import { Button } from "@/components/ui/button";

/** Draft of one prompt or reference file; Save commits it as a new version (REQ-42, REQ-43). */
export function PromptEditor({ file }: { file: PromptFile }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(file.content);
  const save = useMutation({
    mutationFn: () =>
      putJson<PromptFile>(fileUrl(file.agent, file.path), { content: draft, base_version: file.version }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["prompt"] });
      void queryClient.invalidateQueries({ queryKey: ["prompt-history"] });
    },
  });
  return (
    <div className="flex flex-col gap-2">
      <label className="flex flex-col gap-1 text-sm">
        Content
        <textarea
          className="min-h-96 rounded-md border border-border bg-background p-2 font-mono text-sm"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
      </label>
      <div className="flex items-center gap-3">
        <Button size="sm" disabled={save.isPending || draft === file.content} onClick={() => save.mutate()}>
          Save
        </Button>
        {save.isError && <span className="text-destructive text-sm">{save.error.message}</span>}
      </div>
    </div>
  );
}
