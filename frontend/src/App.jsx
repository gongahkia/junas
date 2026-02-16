import { useState, useEffect } from 'react';
import LiveView from './pages/LiveView';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

function App() {
  const [healthStatus, setHealthStatus] = useState(null);
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const resp = await fetch(`${API_URL}/health`);
        const data = await resp.json();
        setHealthStatus(data);
      } catch (e) {
        setHealthStatus({ status: 'error', message: 'Cannot reach server' });
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (darkMode) {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }
  }, [darkMode]);

  const getHealthDot = () => {
    if (!healthStatus) return '🟡';
    if (healthStatus.status === 'ok') return '🟢';
    if (healthStatus.status === 'degraded') return '🟠';
    return '🔴';
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <div className="title-section">
            <h1 className="app-title">
              <span className="title-icon">🍱</span>
              cAI-png
              <span className="version-badge">v2.0</span>
            </h1>
            <p className="app-subtitle">Real-time Food Analysis & Nutrition Tracker</p>
          </div>
          <div className="header-controls">
            <div className="health-indicator" title={healthStatus?.message || 'Checking...'}>
              <span className="health-dot">{getHealthDot()}</span>
              <span className="health-text">{healthStatus?.status || 'checking'}</span>
            </div>
            <button 
              className="theme-toggle"
              onClick={() => setDarkMode(!darkMode)}
              aria-label="Toggle dark mode"
            >
              {darkMode ? '☀️' : '🌙'}
            </button>
          </div>
        </div>
      </header>
      <main className="app-main">
        <LiveView />
      </main>
      <footer className="app-footer">
        <p>Powered by AI • Real-time ML Detection • Gemini Nutrition Analysis</p>
      </footer>
    </div>
  );
}

export default App;

