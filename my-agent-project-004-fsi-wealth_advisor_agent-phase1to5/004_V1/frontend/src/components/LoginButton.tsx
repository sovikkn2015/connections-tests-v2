/**
 * Salesforce OAuth login screen — shown when not authenticated.
 * Full-page centered card with SLDS styling.
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
        <div className="slds-card__header slds-grid">
          <header className="slds-media slds-media_center slds-has-flexi-truncate">
            <div className="slds-media__figure">
              <span
                className="slds-icon_container slds-icon-standard-account"
                title="Wealth Advisor"
              >
                <svg className="slds-icon slds-icon_small" aria-hidden="true">
                  <use xlinkHref="/assets/icons/standard-sprite/svg/symbols.svg#account" />
                </svg>
              </span>
            </div>
            <div className="slds-media__body">
              <h2 className="slds-card__header-title slds-text-heading_small">
                Wealth Advisor Workbench
              </h2>
            </div>
          </header>
        </div>
        <div className="slds-card__body slds-card__body_inner slds-text-align_center">
          <p className="slds-m-bottom_medium slds-text-body_regular">
            Sign in with your Salesforce account to access the wealth advisor agent.
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
