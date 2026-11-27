/** `/api/agents/<agent>/<kind>?path=<path>` with the path encoded. */
export function fileUrl(agent: string, path: string, kind: "file" | "history" | "rollback" = "file"): string {
  return `/api/agents/${encodeURIComponent(agent)}/${kind}?path=${encodeURIComponent(path)}`;
}
