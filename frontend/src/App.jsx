import { useState, useEffect } from 'react';
import LiveView from './pages/LiveView';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

function App() {
  const [healthStatus, setHealthStatus] = useState(null);

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

  const getHealthDot = () => {
    if (!healthStatus) return '\u25CF'; // filled circle
    if (healthStatus.status === 'ok') return '\u25CF';
    if (healthStatus.status === 'degraded') return '\u25CF';
    return '\u25CF';
  };

  const getHealthColor = () => {
    if (!healthStatus) return '#f59e0b';
    if (healthStatus.status === 'ok') return '#22c55e';
    if (healthStatus.status === 'degraded') return '#f59e0b';
    return '#ef4444';
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <div className="title-section">
            <h1 className="app-title">
              cAIpng
              <span className="version-badge">v2.0</span>
            </h1>
          </div>
          <div className="header-controls">
            <div className="health-indicator" title={healthStatus?.message || 'Checking...'}>
              <span className="health-dot" style={{ color: getHealthColor() }}>{getHealthDot()}</span>
              <span className="health-text">{healthStatus?.status || 'checking'}</span>
            </div>
          </div>
        </div>
      </header>
      <main className="app-main">
        <LiveView />
      </main>
      <footer className="app-footer">
        <p>made by <a href="https://gabrielongzm.com">gabriel ong</a> {'\u00B7'} source code <a href="https://github.com/gongahkia/caipng">here</a></p>
      </footer>
    </div>
  );
}

export default App;
