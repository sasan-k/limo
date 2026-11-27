import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getJson } from "@/api/client";
import type { Project } from "@/api/types";

/** Project list plus the chosen project (the first one until the user picks another). */
export function useChosenProject() {
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => getJson<Project[]>("/api/projects") });
  const [chosen, setChosen] = useState<string | null>(null);
  const project = chosen ?? projects.data?.[0]?.name ?? null;
  const names = projects.data?.map((p) => p.name) ?? [];
  return { projects, names, project, setProject: setChosen };
}
