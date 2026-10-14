/**
 * Salesforce-style login page — gradient background with centered card.
 */

interface Props {
  onLogin: () => void;
}

export default function LoginButton({ onLogin }: Props) {
  return (
    <div className="wa-login-page">
      <div className="wa-login-card">
        <div className="wa-login-logo" style={{ marginBottom: '1.5rem' }}>
          <svg width="64" height="44" viewBox="0 0 24 18" fill="none" aria-hidden="true">
            <path d="M19.35 6.04C18.67 2.59 15.64 0 12 0 9.11 0 6.6 1.64 5.35 4.04 2.34 4.36 0 6.91 0 10c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96z" fill="#0176D3"/>
          </svg>
        </div>
        <h1 className="wa-login-title">Wealth Advisor Workbench</h1>
        <p className="wa-login-subtitle">
          Sign in with your Salesforce account to access the AI-powered wealth advisor agent.
        </p>
        <button className="wa-login-btn" onClick={() => onLogin()} aria-label="Sign in with Salesforce">
          Sign in with Salesforce
        </button>
        <div className="wa-login-footer">
          <p>Powered by Agentforce + Data Cloud</p>
          <div className="wa-login-badge">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z" fill="#04844B"/>
              <path d="M10 15.5l-3.5-3.5 1.41-1.41L10 12.67l5.59-5.59L17 8.5l-7 7z" fill="#fff"/>
            </svg>
            Enterprise Security
          </div>
        </div>
      </div>
    </div>
  );
}
