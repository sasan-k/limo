import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getJson } from "@/api/client";
import { fileUrl } from "@/api/prompts";
import type { Agent, PromptFile } from "@/api/types";
import { PromptEditor } from "@/components/PromptEditor";
import { PromptHistory } from "@/components/PromptHistory";

function Select(props: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      {props.label}
      <select
        className="rounded-md border border-border bg-background px-2 py-1"
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
      >
        {props.options.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}

/** View and edit each agent's prompt and reference files, with versions (REQ-42, REQ-43). */
export function PromptsPage() {
  const [agent, setAgent] = useState("build");
  const [path, setPath] = useState("SKILL.md");
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => getJson<Agent[]>("/api/agents") });
  const files = useQuery({
    queryKey: ["prompt-files", agent],
    queryFn: () => getJson<string[]>(`/api/agents/${encodeURIComponent(agent)}/files`),
  });
  const file = useQuery({
    queryKey: ["prompt", agent, path],
    queryFn: () => getJson<PromptFile>(fileUrl(agent, path)),
  });
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-4">
        <Select
          label="Agent"
          value={agent}
          options={agents.data?.map((a) => a.name) ?? [agent]}
          onChange={(v) => {
            setAgent(v);
            setPath("SKILL.md");
          }}
        />
        <Select label="File" value={path} options={files.data ?? [path]} onChange={setPath} />
      </div>
      {file.isError && <p className="text-destructive">{file.error.message}</p>}
      {file.data && (
        <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
          <PromptEditor key={`${agent}/${path}/${file.data.version}`} file={file.data} />
          <PromptHistory agent={agent} path={path} />
        </div>
      )}
    </div>
  );
}
