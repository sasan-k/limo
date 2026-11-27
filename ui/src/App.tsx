import { useLiveEvents } from "@/api/events";
import { ThemeToggle } from "@/components/ThemeToggle";
import { AgentsPage } from "@/pages/AgentsPage";

export function App() {
  useLiveEvents();
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="flex items-center justify-between border-b border-border px-6 py-3">
        <h1 className="text-lg font-semibold">Limo</h1>
        <ThemeToggle />
      </header>
      <main className="p-6">
        <AgentsPage />
      </main>
    </div>
  );
}
