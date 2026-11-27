import { formatUsd } from "@/lib/format";

/** One cost total as a two-column table: label → dollars. */
export function CostTable({ title, rows }: { title: string; rows: Array<[string, string]> }) {
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <h2 className="font-semibold">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">No cost yet.</p>
      ) : (
        <table className="text-sm">
          <tbody>
            {rows.map(([label, amount]) => (
              <tr key={label} className="border-b border-border">
                <th scope="row" className="py-1 pr-4 text-left font-normal">
                  {label}
                </th>
                <td className="py-1 text-right font-mono">{formatUsd(amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
