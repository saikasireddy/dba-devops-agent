import { useState } from 'react'

function App() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [needsApproval, setNeedsApproval] = useState(false)
  const [sqlProposed, setSqlProposed] = useState(null)
  const [schemaInput, setSchemaInput] = useState("CREATE TABLE orders (\n  id SERIAL PRIMARY KEY,\n  user_id INT,\n  amount DECIMAL\n);")
  const [mode, setMode] = useState('schema') // 'schema' or 'live'

  const runAnalysis = async (action = 'start') => {
    setLoading(true)
    if (action === 'start') {
      setResult(null)
      setNeedsApproval(false)
    }
    
    try {
      const response = await fetch('http://localhost:8000/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          schema_sql: mode === 'schema' ? schemaInput : "",
          thread_id: "demo_session_1",
          action: action
        })
      })
      
      const data = await response.json()
      setResult(data.recommendation)
      setNeedsApproval(data.needs_approval)
      setSqlProposed(data.sql_proposed)
    } catch (error) {
      setResult(`Error connecting to AI Agent: ${error.message}\nMake sure the FastAPI server is running on port 8000!`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="dashboard-container">
      
      {/* Left Control Panel */}
      <div className="glass-panel">
        <h1>Cockroach DevOps</h1>
        <div className="subtitle">Autonomous Database Agent</div>
        
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-value success">
              <span className="pulse-dot"></span> 99.9%
            </div>
            <div className="metric-label">Uptime</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">1.2ms</div>
            <div className="metric-label">P99 Latency</div>
          </div>
        </div>

        <div className="mode-selector">
          <button 
            className={`mode-btn ${mode === 'schema' ? 'active' : ''}`}
            onClick={() => setMode('schema')}
          >
            Test Schema
          </button>
          <button 
            className={`mode-btn ${mode === 'live' ? 'active' : ''}`}
            onClick={() => setMode('live')}
          >
            Live Cluster
          </button>
        </div>

        {mode === 'schema' && (
          <textarea 
            className="sql-input fade-in"
            value={schemaInput}
            onChange={(e) => setSchemaInput(e.target.value)}
            placeholder="Enter SQL schema to analyze..."
          />
        )}

        <button 
          className="primary-btn" 
          onClick={() => runAnalysis('start')}
          disabled={loading || needsApproval}
        >
          {loading ? 'Analyzing Cluster...' : 'Run AI Diagnostics'}
        </button>
      </div>

      {/* Right Terminal Panel */}
      <div className="glass-panel terminal-wrapper">
        <div className="terminal-header">
          <div className="mac-dots">
            <div className="mac-btn close"></div>
            <div className="mac-btn minimize"></div>
            <div className="mac-btn maximize"></div>
          </div>
          <div className="terminal-title">agent@cockroach-cloud:~</div>
        </div>
        
        <div className="terminal-window">
          {loading ? (
            <div className="fade-in">
              <div style={{color: '#8b5cf6'}}>$ Initialize Neural Engine...</div>
              <div style={{color: '#3b82f6'}}>$ Booting Multi-Agent Graph (DBA & QA)...</div>
              <div style={{color: '#a78bfa'}}>$ Retrieving Memory Context...</div>
              <div className="loader-bar"><div className="loader-progress"></div></div>
            </div>
          ) : result ? (
            <div className="fade-in" style={{whiteSpace: 'pre-wrap'}}>
              <span style={{color: '#10b981', fontWeight: 600}}>✓ Graph Execution Paused / Finished:</span>
              <br/><br/>
              {result}
              
              {needsApproval && (
                <div style={{marginTop: '2rem', padding: '1rem', border: '1px solid #f59e0b', borderRadius: '12px', background: 'rgba(245, 158, 11, 0.1)'}}>
                  <h3 style={{color: '#d97706', marginTop: 0}}>⚠️ Human-in-the-Loop Required</h3>
                  <p style={{color: '#334155'}}>The QA Agent has approved the following SQL, but it requires human permission to execute on the live database:</p>
                  <pre style={{margin: '1rem 0'}}><code>{sqlProposed}</code></pre>
                  <button 
                    onClick={() => runAnalysis('resume')}
                    style={{padding: '0.8rem 1.5rem', background: '#10b981', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold'}}
                  >
                    Approve & Execute SQL
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div style={{color: 'rgba(255,255,255,0.3)', textAlign: 'center', marginTop: '120px'}}>
              Awaiting diagnostic execution...<br/>
              Click "Run AI Diagnostics" to begin.
            </div>
          )}
        </div>
      </div>

    </div>
  )
}

export default App
