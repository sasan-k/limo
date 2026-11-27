import type { BoardTicket } from "@/api/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** One ticket on the board: id, title and the tickets it depends on (REQ-40). */
export function TicketCard({ ticket }: { ticket: BoardTicket }) {
  return (
    <Card data-testid={`ticket-${ticket.id}`} className="gap-2 py-3">
      <CardHeader className="px-3">
        <CardTitle className="text-sm">{ticket.id}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1 px-3 text-sm">
        <span>{ticket.title}</span>
        {ticket.depends_on.length > 0 && (
          <CardDescription>depends on {ticket.depends_on.join(", ")}</CardDescription>
        )}
      </CardContent>
    </Card>
  );
}
