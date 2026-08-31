import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import App from './App';
import OwnerGate from './components/OwnerGate';
import { AppearanceProvider } from './appearance/AppearanceProvider';
import { LanguageProvider } from './i18n';
import './styles/index.css';
import 'highlight.js/styles/github-dark.css';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <LanguageProvider>
      <AppearanceProvider>
        <BrowserRouter>
          <OwnerGate>
            <App />
          </OwnerGate>
        </BrowserRouter>
      </AppearanceProvider>
    </LanguageProvider>
  </React.StrictMode>,
);
