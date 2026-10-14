import { CheckCircle, Shield, Eye } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { Badge } from "@/components/shared/Badge";
import { Button } from "@/components/shared/Button";
import type { ReviewItem } from "@/api/types";

interface Props { item: ReviewItem; onApprove: (id: string) => void; onReject: (id: string, reason: string) => void; }

export function ReviewDetail({ item, onApprove, onReject }: Props) {
  return (
    <div className="p-4 overflow-y-auto h-full space-y-4">
      <Card>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">Agent Output (what client sees)</h3>
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{item.agentOutput}</p>
      </Card>
      <Card>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">Compliance Context</h3>
        <div className="text-sm space-y-1.5">
          <div className="flex items-center gap-2"><span className="text-gray-500 w-24">OPA Decision:</span><Badge variant={item.opaDecision === "ALLOW" ? "success" : item.opaDecision === "DENY" ? "danger" : "warning"}>{item.opaDecision}</Badge></div>
          <div className="flex items-center gap-2"><span className="text-gray-500 w-24">Rule:</span><span className="font-mono text-xs">{item.opaRule}</span></div>
          <div className="flex items-center gap-2"><span className="text-gray-500 w-24">WSP Section:</span><span>{item.wspSection}</span></div>
          <div className="flex items-center gap-2"><span className="text-gray-500 w-24">MNPI Stripped:</span><div className="flex gap-1">{item.mnpiStripped.map((f) => <Badge key={f} variant="mnpi">{f}</Badge>)}</div></div>
          <div className="flex items-center gap-2"><span className="text-gray-500 w-24">Leakage Scan:</span><Badge variant={item.leakageScan === "pass" ? "success" : "danger"}>{item.leakageScan === "pass" ? "PASS" : "FAIL"}</Badge></div>
          <div className="flex items-center gap-2"><span className="text-gray-500 w-24">Smarsh:</span><Badge variant="neutral">{item.smarchArchive === "archived" ? "Archived" : "Pending"}</Badge></div>
        </div>
      </Card>
      <Card>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">Advisor</h3>
        <p className="text-sm">{item.advisorName} · CRD# {item.advisorCrd}</p>
        <p className="text-sm text-gray-500">Client: {item.clientName} ({item.clientId})</p>
      </Card>
      <div className="flex gap-2">
        <Button onClick={() => onApprove(item.id)}><CheckCircle className="w-4 h-4" aria-hidden="true" />Approve</Button>
        <Button variant="danger" onClick={() => onReject(item.id, "Rejected by principal")}><Shield className="w-4 h-4" aria-hidden="true" />Reject + Reason</Button>
        <Button variant="secondary"><Eye className="w-4 h-4" aria-hidden="true" />Edit and Approve</Button>
      </div>
    </div>
  );
}
