import { OrderReviewCard } from "@/components/detail/OrderReviewCard";
import { mockOrderReview } from "@/mock/mockData";
import * as gateway from "@/api/gateway";
import { useAppStore } from "@/store/useAppStore";

export function OrderApprovalPage() {
  const addNotification = useAppStore((s) => s.addNotification);
  return (
    <div className="max-w-3xl mx-auto p-4 h-full">
      <OrderReviewCard data={mockOrderReview}
        onApprove={(id) => { void gateway.approveOrder(id); addNotification({ type: "success", title: "Order Approved", message: `Order ${id} approved.` }); }}
        onReject={(id, reason) => { void gateway.rejectOrder(id, reason); addNotification({ type: "info", title: "Order Rejected", message: `Order ${id} rejected: ${reason}` }); }} />
    </div>
  );
}
