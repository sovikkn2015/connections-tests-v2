/**
 * Salesforce OAuth login screen — shown when not authenticated.
 */

interface Props {
  onLogin: () => void;
}

export default function LoginButton({ onLogin }: Props) {
  return (
    <div
      className="slds-grid slds-grid_align-center slds-grid_vertical-align-center"
      style={{ height: '100vh', background: '#f4f6f9' }}
    >
      <div className="slds-card" style={{ width: '24rem', padding: '2rem' }}>
        <div className="slds-card__header slds-text-align_center">
          <h2 className="slds-card__header-title slds-text-heading_small">
            FSI Research Workbench
          </h2>
          <p className="slds-text-body_small slds-text-color_weak slds-m-top_xx-small">
            Powered by OpenClaw
          </p>
        </div>
        <div className="slds-card__body slds-card__body_inner slds-text-align_center">
          <p className="slds-m-bottom_medium slds-text-body_regular">
            Sign in with your Salesforce account to access the research agent.
          </p>
          <button
            className="slds-button slds-button_brand"
            onClick={() => onLogin()}
            aria-label="Sign in with Salesforce"
          >
            Sign in with Salesforce
          </button>
        </div>
      </div>
    </div>
  );
}
