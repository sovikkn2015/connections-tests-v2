import type { DetailType, MeetingPrep, PortfolioSummary, OrderReview, ResearchBrief } from "@/api/types";
import { MeetingPrepCard } from "./MeetingPrepCard";
import { PortfolioView } from "./PortfolioView";
import { OrderReviewCard } from "./OrderReviewCard";
import { ResearchBriefCard } from "./ResearchBriefCard";
import { EmptyState } from "./EmptyState";

interface Props {
  detailType: DetailType | null;
  payload: unknown;
  onApproveOrder?: (orderId: string) => void;
  onRejectOrder?: (orderId: string, reason: string) => void;
}

export function DetailPanel({ detailType, payload, onApproveOrder, onRejectOrder }: Props) {
  if (!detailType || detailType === "empty") return <EmptyState />;
  switch (detailType) {
    case "meeting_prep": return <MeetingPrepCard data={payload as MeetingPrep} />;
    case "portfolio": return <PortfolioView data={payload as PortfolioSummary} />;
    case "order_review": return <OrderReviewCard data={payload as OrderReview} onApprove={onApproveOrder} onReject={onRejectOrder} />;
    case "research_brief": return <ResearchBriefCard data={payload as ResearchBrief} />;
    default: return <EmptyState />;
  }
}
