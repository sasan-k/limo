import { useQuery } from "@tanstack/react-query";

import { getJson } from "@/api/client";
import type { InboxItem } from "@/api/types";
import { InboxEntry } from "@/components/InboxEntry";

/** Tickets waiting for a human: escalations and budget holds (REQ-41). */
export function InboxPage() {
  const items = useQuery({ queryKey: ["inbox"], queryFn: () => getJson<InboxItem[]>("/api/inbox") });
  if (items.isPending) return <p className="text-muted-foreground">Loading inbox…</p>;
  if (items.isError) return <p className="text-destructive">Could not load the inbox.</p>;
  if (items.data.length === 0) return <p className="text-muted-foreground">Nothing waiting for you.</p>;
  return (
    <section aria-label="inbox" className="grid gap-4 lg:grid-cols-2">
      {items.data.map((item) => (
        <InboxEntry key={item.id} item={item} />
      ))}
    </section>
  );
}
