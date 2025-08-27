import React, { useEffect, useState } from 'react';

export const App: React.FC = () => {
  const [health, setHealth] = useState<string>('checking');
  const [error, setError] = useState<string | null>(null);
  const apiBase = (import.meta as any).env?.VITE_API_BASE || '';

  useEffect(() => {
    const url = apiBase ? `${apiBase.replace(/\/$/, '')}/health` : '/health';
    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => setHealth(d.status))
      .catch(e => { setHealth('error'); setError(e.message); });
  }, [apiBase]);

  return (
    <main style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
      <h1>SKCC Awards</h1>
      <p>Backend health: <strong>{health}</strong></p>
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
    </main>
  );
};

export default App;
