import { Calendar, User, Target, DollarSign, CheckCircle, AlertTriangle, FileText, Send, Edit } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { Badge } from "@/components/shared/Badge";
import { Button } from "@/components/shared/Button";
import type { MeetingPrep } from "@/api/types";

interface Props { data: MeetingPrep; }

export function MeetingPrepCard({ data }: Props) {
  return (
    <Card className="overflow-y-auto h-full">
      <div className="flex items-center gap-2 mb-4">
        <FileText className="w-5 h-5 text-blue-700 dark:text-blue-400" aria-hidden="true" />
        <h2 className="text-lg font-semibold">Meeting Prep</h2>
      </div>
      <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
        <div className="flex items-center gap-2"><User className="w-4 h-4 text-gray-400" aria-hidden="true" /><span>{data.clientName}</span></div>
        <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-gray-400" aria-hidden="true" /><span>{data.meetingDate}</span></div>
        <div className="flex items-center gap-2"><Target className="w-4 h-4 text-gray-400" aria-hidden="true" /><span>Risk: {data.riskProfile} · {data.objective}</span></div>
        <div className="flex items-center gap-2"><DollarSign className="w-4 h-4 text-gray-400" aria-hidden="true" /><span>AUM: {data.aum}</span></div>
      </div>
      <div className="mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">Top Holdings</h3>
        <div className="space-y-1">
          {data.holdings.map((h) => (
            <div key={h.symbol} className="flex items-center justify-between text-sm py-1">
              <span className="font-medium w-16">{h.symbol}</span>
              <span className="text-gray-500 w-12 text-right">{h.allocation}%</span>
              <span className={`w-16 text-right ${h.ytdReturn >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                {h.ytdReturn > 0 ? "+" : ""}{h.ytdReturn}%
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">Talking Points</h3>
        <ul className="space-y-1.5">
          {data.talkingPoints.map((tp, i) => (<li key={i} className="text-sm flex gap-2"><span className="text-gray-400 shrink-0">•</span><span>{tp}</span></li>))}
        </ul>
      </div>
      <div className="mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">Compliance Notes</h3>
        <div className="space-y-1.5">
          {data.complianceNotes.map((cn, i) => (
            <div key={i} className="flex items-start gap-2 text-sm">
              {cn.status === "pass" ? <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400 shrink-0 mt-0.5" aria-hidden="true" /> : <AlertTriangle className="w-4 h-4 text-yellow-600 dark:text-yellow-400 shrink-0 mt-0.5" aria-hidden="true" />}
              <span>{cn.text}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="mb-4"><div className="flex flex-wrap gap-1">{data.sources.map((s) => (<Badge key={s.name} variant="neutral">{s.name}</Badge>))}</div></div>
      <div className="flex gap-2 pt-2 border-t border-gray-200 dark:border-gray-700">
        <Button size="sm"><Send className="w-3.5 h-3.5" aria-hidden="true" />Send to Client</Button>
        <Button variant="secondary" size="sm"><FileText className="w-3.5 h-3.5" aria-hidden="true" />PDF</Button>
        <Button variant="ghost" size="sm"><Edit className="w-3.5 h-3.5" aria-hidden="true" />Edit</Button>
      </div>
    </Card>
  );
}
