import { ReviewQueue } from "@/components/review/ReviewQueue";
import { ReviewDetail } from "@/components/review/ReviewDetail";
import { useReviewQueue } from "@/hooks/useReviewQueue";

export function ReviewQueuePage() {
  const { items, selected, selectedId, select, approve, reject } = useReviewQueue();
  return (
    <div className="flex h-full">
      <div className="w-full md:w-2/5 border-r border-gray-200 dark:border-gray-700">
        <ReviewQueue items={items} selectedId={selectedId} onSelect={select} />
      </div>
      <div className="hidden md:flex md:w-3/5 flex-col">
        {selected ? <ReviewDetail item={selected} onApprove={approve} onReject={reject} /> : (
          <div className="flex items-center justify-center h-full text-gray-400"><p className="text-sm">Select a review to see details</p></div>
        )}
      </div>
    </div>
  );
}
