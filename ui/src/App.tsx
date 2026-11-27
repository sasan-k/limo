import { useState } from "react";

import { useLiveEvents } from "@/api/events";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { AgentsPage } from "@/pages/AgentsPage";
import { BoardPage } from "@/pages/BoardPage";
import { InboxPage } from "@/pages/InboxPage";

const PAGES = { Agents: AgentsPage, Board: BoardPage, Inbox: InboxPage };
type PageName = keyof typeof PAGES;

export function App() {
  useLiveEvents();
  const [page, setPage] = useState<PageName>("Agents");
  const Page = PAGES[page];
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="flex items-center justify-between gap-4 border-b border-border px-6 py-3">
        <h1 className="text-lg font-semibold">Limo</h1>
        <nav className="flex gap-1">
          {(Object.keys(PAGES) as PageName[]).map((name) => (
            <Button
              key={name}
              variant={name === page ? "default" : "ghost"}
              size="sm"
              aria-current={name === page ? "page" : undefined}
              onClick={() => setPage(name)}
            >
              {name}
            </Button>
          ))}
        </nav>
        <ThemeToggle />
      </header>
      <main className="p-6">
        <Page />
      </main>
    </div>
  );
}
