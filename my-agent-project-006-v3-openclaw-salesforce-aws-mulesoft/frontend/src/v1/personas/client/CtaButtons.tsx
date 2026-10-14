/**
 * "Schedule call" / "Ask RM" CTA buttons. Every client turn offers these
 * per the liaison-orchestrator contract (narrative §1).
 */

export interface CtaButtonsProps {
  onScheduleCall: () => void;
  onAskRm: () => void;
}

export function CtaButtons({ onScheduleCall, onAskRm }: CtaButtonsProps) {
  return (
    <div className="client-ctas" role="group" aria-label="Client actions">
      <button type="button" onClick={onScheduleCall}>
        Schedule call
      </button>
      <button type="button" onClick={onAskRm} data-variant="secondary">
        Ask RM
      </button>
    </div>
  );
}
