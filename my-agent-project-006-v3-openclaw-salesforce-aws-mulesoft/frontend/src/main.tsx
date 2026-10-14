import React from 'react';
import ReactDOM from 'react-dom/client';

// SLDS base CSS — must be imported before app components.
import '@salesforce-ux/design-system/assets/styles/salesforce-lightning-design-system.min.css';

import './v1/styles/global.css';
import './v1/styles/research.css';
import './v1/styles/advisor.css';
import './v1/styles/client.css';
import './v1/styles/traversal-map.css';

import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
