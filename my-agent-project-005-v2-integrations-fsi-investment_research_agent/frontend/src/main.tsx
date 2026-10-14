import React from 'react';
import ReactDOM from 'react-dom/client';

// SLDS CSS — must be imported before app components
import '@salesforce-ux/design-system/assets/styles/salesforce-lightning-design-system.min.css';

import './styles/slds-overrides.css';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
