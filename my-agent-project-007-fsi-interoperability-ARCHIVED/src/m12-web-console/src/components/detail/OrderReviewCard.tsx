import { useState } from "react";
import { ShoppingCart, CheckCircle, AlertTriangle, XCircle, Clock } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { Badge } from "@/components/shared/Badge";
import { Button } from "@/components/shared/Button";
import type { OrderReview } from "@/api/types";

interface Props {
  data: OrderReview;
  onApprove?: (orderId: string) => void;
  onReject?: (orderId: string, reason: string) => void;
}

export function OrderReviewCard({ data, onApprove, onReject }: Props) {
  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);
  const hasFailure = data.complianceChecks.some((c) => c.status === "fail");
  const timeLeft = Math.max(0, Math.floor((new Date(data.expiresAt).getTime() - Date.now()) / 3600000));

  return (
    <Card variant="highlighted" className="overflow-y-auto h-full">
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle className="w-5 h-5 text-yellow-600" aria-hidden="true" />
        <h2 className="text-lg font-semibold">Order Requires Your Approval</h2>
      </div>
      <div className="flex items-center gap-3 mb-4">
        <Badge variant={data.side === "BUY" ? "success" : "danger"}>{data.side}</Badge>
        <span className="text-lg font-semibold">{data.quantity} shares · {data.symbol} ({data.securityName})</span>
      </div>
      <div className="text-sm text-gray-600 dark:text-gray-400 mb-4 space-y-1">
        <p>Order Type: {data.orderType}</p>
        <p>Account: {data.account} · {data.custodian}</p>
      </div>
      <div className="mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">Client Context</h3>
        <div className="text-sm space-y-1">
          <p>{data.clientName} · {data.riskProfile} Risk · {data.objective}</p>
          <p>Current {data.symbol}: {data.currentHolding.shares} shares ({data.currentHolding.allocation}%)</p>
          <p>Post-trade {data.symbol}: {data.postTradeHolding.shares} shares ({data.postTradeHolding.allocation}%)</p>
        </div>
      </div>
      <div className="mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">Compliance Checks</h3>
        <div className="space-y-1.5">
          {data.complianceChecks.map((check) => (
            <div key={check.name} className="flex items-center gap-2 text-sm">
              {check.status === "pass" ? <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" aria-hidden="true" /> :
               check.status === "warning" ? <AlertTriangle className="w-4 h-4 text-yellow-600 dark:text-yellow-400" aria-hidden="true" /> :
               <XCircle className="w-4 h-4 text-red-600 dark:text-red-400" aria-hidden="true" />}
              <span className="font-medium w-28">{check.name}</span>
              <span className="text-gray-600 dark:text-gray-400">{check.detail}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">Cost Impact</h3>
        <div className="text-sm space-y-1">
          <p>Estimated Cost: {data.estimatedCost}</p>
          <p>Cost Basis Method: <span className="font-mono">{data.costBasisMethod}</span></p>
          <p>Tax Lot: {data.taxLotNote}</p>
        </div>
      </div>
      {showReject && (
        <div className="mb-4">
          <textarea value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder="Reason for rejection..." className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm" rows={2} />
        </div>
      )}
      <div className="flex gap-2 pt-3 border-t border-gray-200 dark:border-gray-700">
        <Button onClick={() => onApprove?.(data.orderId)} disabled={hasFailure}><CheckCircle className="w-4 h-4" aria-hidden="true" />Approve Order</Button>
        {showReject ? (
          <Button variant="danger" onClick={() => { onReject?.(data.orderId, rejectReason); setShowReject(false); }}><XCircle className="w-4 h-4" aria-hidden="true" />Confirm Reject</Button>
        ) : (
          <Button variant="danger" onClick={() => setShowReject(true)}><XCircle className="w-4 h-4" aria-hidden="true" />Reject Order</Button>
        )}
        <Button variant="secondary"><ShoppingCart className="w-4 h-4" aria-hidden="true" />Request Changes</Button>
      </div>
      <div className="flex items-center gap-1 mt-3 text-xs text-gray-500">
        <Clock className="w-3.5 h-3.5" aria-hidden="true" /><span>Auto-cancels in {timeLeft}h without approval</span>
      </div>
    </Card>
  );
}
