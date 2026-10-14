import { BookOpen, ExternalLink } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { Badge } from "@/components/shared/Badge";
import type { ResearchBrief } from "@/api/types";

interface Props { data: ResearchBrief; }

export function ResearchBriefCard({ data }: Props) {
  return (
    <Card className="overflow-y-auto h-full">
      <div className="flex items-center gap-2 mb-2">
        <BookOpen className="w-5 h-5 text-blue-700 dark:text-blue-400" aria-hidden="true" />
        <h2 className="text-lg font-semibold">{data.title}</h2>
      </div>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">{data.summary}</p>
      <div className="mb-3"><Badge variant="info">Confidence: {Math.round(data.confidenceScore * 100)}%</Badge></div>
      <div className="space-y-4 mb-4">
        {data.sections.map((sec, i) => (
          <div key={i}>
            <h3 className="text-sm font-semibold mb-1">{sec.heading}</h3>
            <p className="text-sm text-gray-700 dark:text-gray-300">{sec.content}</p>
            {sec.citation && <p className="text-xs text-gray-500 mt-1 flex items-center gap-1"><ExternalLink className="w-3 h-3" aria-hidden="true" />{sec.citation}</p>}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-1 pt-2 border-t border-gray-200 dark:border-gray-700">
        {data.sources.map((s) => <Badge key={s.name} variant="neutral">{s.name}</Badge>)}
      </div>
    </Card>
  );
}
