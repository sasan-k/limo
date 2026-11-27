import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getJson, putJson } from "@/api/client";
import type { RunnerSwitch as RunnerSwitchState } from "@/api/types";
import { Button } from "@/components/ui/button";

/** Header switch that turns the runner on and off; the engine starts with it off (REQ-46). */
export function RunnerSwitch() {
  const queryClient = useQueryClient();
  const state = useQuery({ queryKey: ["runner"], queryFn: () => getJson<RunnerSwitchState>("/api/runner") });
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => putJson<RunnerSwitchState>("/api/runner", { enabled }),
    onSuccess: (data) => queryClient.setQueryData(["runner"], data),
  });
  const on = state.data?.enabled === true;
  return (
    <div className="flex items-center gap-2">
      {toggle.isError && <span className="text-destructive text-sm">{toggle.error.message}</span>}
      <Button
        variant={on ? "default" : "outline"}
        size="sm"
        aria-pressed={on}
        disabled={!state.isSuccess || toggle.isPending}
        onClick={() => toggle.mutate(!on)}
      >
        Runner {on ? "on" : "off"}
      </Button>
    </div>
  );
}
