import { PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { Card } from "@/components/shared/Card";
import type { PortfolioSummary } from "@/api/types";

interface Props { data: PortfolioSummary; }

export function PortfolioView({ data }: Props) {
  return (
    <Card className="overflow-y-auto h-full">
      <h2 className="text-lg font-semibold mb-1">{data.clientName} — Portfolio</h2>
      <div className="flex gap-4 text-sm text-gray-600 dark:text-gray-400 mb-4">
        <span>Total: {data.totalValue}</span>
        <span className={data.ytdReturn >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>
          YTD: {data.ytdReturn > 0 ? "+" : ""}{data.ytdReturn}%
        </span>
      </div>
      <div className="mb-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-gray-500 border-b border-gray-200 dark:border-gray-700">
            <th className="py-1.5 font-medium">Symbol</th><th className="py-1.5 font-medium">Name</th>
            <th className="py-1.5 font-medium text-right">Alloc %</th><th className="py-1.5 font-medium text-right">YTD</th>
            <th className="py-1.5 font-medium text-right">Cost Basis</th>
          </tr></thead>
          <tbody>{data.holdings.map((h) => (
            <tr key={h.symbol} className="border-b border-gray-100 dark:border-gray-800">
              <td className="py-1.5 font-medium">{h.symbol}</td>
              <td className="py-1.5 text-gray-600 dark:text-gray-400">{h.name}</td>
              <td className="py-1.5 text-right">{h.allocation}%</td>
              <td className={`py-1.5 text-right ${h.ytdReturn >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>{h.ytdReturn > 0 ? "+" : ""}{h.ytdReturn}%</td>
              <td className="py-1.5 text-right font-mono text-xs">{h.costBasisMethod}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">Allocation</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart><Pie data={data.allocation} dataKey="value" nameKey="category" cx="50%" cy="50%" outerRadius={70} label={({ category, value }) => `${category} ${value}%`}>
              {data.allocation.map((entry, i) => <Cell key={i} fill={entry.color} />)}
            </Pie><Tooltip /></PieChart>
          </ResponsiveContainer>
        </div>
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">Performance</h3>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={data.performance}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} /><Tooltip /><Legend />
              <Line type="monotone" dataKey="portfolio" stroke="#3b82f6" strokeWidth={2} name="Portfolio" />
              <Line type="monotone" dataKey="benchmark" stroke="#94a3b8" strokeWidth={2} strokeDasharray="4 4" name="Benchmark" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Card>
  );
}
