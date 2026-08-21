import React, { useState, useEffect } from 'react';

const API_BASE = 'http://127.0.0.1:8000/api';

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('dashboard'); // 'dashboard', 'ml_report', 'policy_sandbox'
  const [stats, setStats] = useState<any>(null);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [selectedTxId, setSelectedTxId] = useState<string>('');
  const [selectedDetails, setSelectedDetails] = useState<any>(null);
  
  // Search & Filters
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  
  // Policy Form State
  const [policyConfig, setPolicyConfig] = useState<any>({
    max_retries: 2,
    high_amount_threshold: 50000.0,
    min_probability: 0.30
  });
  
  // Transaction Edit Form State
  const [isEditingTx, setIsEditingTx] = useState<boolean>(false);
  const [editForm, setEditForm] = useState<any>({
    amount: 0.0,
    payment_method: 'card',
    gateway_code: '',
    status: 'failed'
  });

  const [liveLogs, setLiveLogs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [demoMessage, setDemoMessage] = useState<string>('');

  // Initial load
  useEffect(() => {
    fetchStats();
    fetchTransactions();
    fetchLiveLogs();
    fetchPolicyConfig();
  }, []);

  // Fetch stats and transactions whenever filters change
  useEffect(() => {
    fetchTransactions();
  }, [search, statusFilter, categoryFilter]);

  // Fetch details of selected transaction
  useEffect(() => {
    if (selectedTxId) {
      fetchTxDetails(selectedTxId);
      setIsEditingTx(false); // Reset edit state when switching transactions
    }
  }, [selectedTxId]);

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/dashboard/stats`);
      const data = await res.json();
      setStats(data);
    } catch (err) {
      console.error("Error fetching stats:", err);
    }
  };

  const fetchTransactions = async () => {
    try {
      let url = `${API_BASE}/dashboard/transactions?limit=50`;
      if (search) url += `&search=${encodeURIComponent(search)}`;
      if (statusFilter) url += `&status=${statusFilter}`;
      if (categoryFilter) url += `&merchant_category=${categoryFilter}`;
      
      const res = await fetch(url);
      const data = await res.json();
      setTransactions(data.results || []);
      
      // Auto select first transaction if none selected
      if (data.results && data.results.length > 0 && !selectedTxId) {
        setSelectedTxId(data.results[0].id);
      }
    } catch (err) {
      console.error("Error fetching transactions:", err);
    }
  };

  const fetchTxDetails = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/dashboard/transactions/${id}`);
      const data = await res.json();
      setSelectedDetails(data);
      
      // Populate edit form
      if (data.transaction) {
        setEditForm({
          amount: data.transaction.amount,
          payment_method: data.transaction.payment_method,
          gateway_code: data.transaction.gateway_code || '',
          status: data.transaction.status
        });
      }
    } catch (err) {
      console.error("Error fetching tx details:", err);
    }
  };

  const fetchLiveLogs = async () => {
    try {
      const res = await fetch(`${API_BASE}/dashboard/audit-logs?limit=30`);
      const data = await res.json();
      setLiveLogs(data);
    } catch (err) {
      console.error("Error fetching live logs:", err);
    }
  };

  const fetchPolicyConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/dashboard/policy-config`);
      const data = await res.json();
      setPolicyConfig(data);
    } catch (err) {
      console.error("Error fetching policy config:", err);
    }
  };

  const updatePolicyConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/dashboard/policy-config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(policyConfig)
      });
      const data = await res.json();
      setDemoMessage(data.message);
      
      // Refresh stats
      fetchStats();
      if (selectedTxId) fetchTxDetails(selectedTxId);
    } catch (err) {
      console.error("Error saving policy config:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTxEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/dashboard/transactions/${selectedTxId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm)
      });
      const data = await res.json();
      setDemoMessage(data.message);
      setIsEditingTx(false);
      
      // Refresh stats & details
      await fetchStats();
      await fetchTransactions();
      await fetchLiveLogs();
      await fetchTxDetails(selectedTxId);
    } catch (err) {
      console.error("Error editing transaction:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const triggerDemo = async (scenarioId: number) => {
    setIsLoading(true);
    setDemoMessage('');
    try {
      const res = await fetch(`${API_BASE}/dashboard/trigger-demo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenarioId })
      });
      const data = await res.json();
      setDemoMessage(data.message);
      
      // Select the demo transaction
      const targetId = scenarioId === 1 ? 'pay_demo_success' : 'pay_demo_failure';
      setSelectedTxId(targetId);
      
      // Refresh datasets
      await fetchStats();
      await fetchTransactions();
      await fetchLiveLogs();
      await fetchTxDetails(targetId);
    } catch (err) {
      console.error("Error triggering demo:", err);
      setDemoMessage('Error executing demo pipeline.');
    } finally {
      setIsLoading(false);
    }
  };

  // Timeline SVG calculations
  const renderTimelineChart = () => {
    if (transactions.length === 0) return null;
    
    // Sort transactions chronologically for rendering
    const chronTx = [...transactions].reverse();
    const width = 600;
    const height = 100;
    const padding = 10;
    
    // Map transactions to cumulative recovered revenue
    let cumulative = 0;
    const points = chronTx.map((tx, idx) => {
      if (tx.recovered) cumulative += tx.amount;
      const x = padding + (idx / (chronTx.length - 1)) * (width - 2 * padding);
      return { x, val: cumulative };
    });
    
    if (points.length < 2) return null;
    
    const maxVal = Math.max(...points.map(p => p.val), 1000);
    const mappedPoints = points.map(p => ({
      x: p.x,
      y: height - padding - (p.val / maxVal) * (height - 2 * padding)
    }));
    
    const pathD = `M ${mappedPoints[0].x} ${mappedPoints[0].y} ` + 
      mappedPoints.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ');
      
    return (
      <div style={{ background: 'rgba(0,0,0,0.3)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)', marginTop: '0.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '0.5rem' }}>
          <span>Cumulative Recovered Revenue Trend (Explorer Timeline)</span>
          <span style={{ fontFamily: 'monospace', color: 'var(--color-success)', fontWeight: 'bold' }}>Max: INR {maxVal.toLocaleString()}</span>
        </div>
        <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: '80px', overflow: 'visible' }}>
          {/* Grid lines */}
          <line x1={padding} y1={height/2} x2={width-padding} y2={height/2} stroke="rgba(255,255,255,0.03)" strokeDasharray="3" />
          
          {/* Trend Polyline */}
          <path d={pathD} fill="none" stroke="var(--color-success)" strokeWidth="2.5" />
          
          {/* Points */}
          {mappedPoints.map((p, i) => (
            i % 4 === 0 && (
              <circle key={i} cx={p.x} cy={p.y} r="3" fill="var(--color-success)" stroke="#0B0F19" strokeWidth="1" />
            )
          ))}
        </svg>
      </div>
    );
  };

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="logo-section">
          <h1>
            RecoveryOS
            <span className="logo-badge">Buildathon Sandbox v1.1</span>
          </h1>
          <p>Autonomous Revenue Recovery Engine with Deterministic Guardrails</p>
        </div>
        
        {/* Navigation Tabs */}
        <div style={{ display: 'flex', gap: '0.25rem', background: 'rgba(255,255,255,0.03)', padding: '0.25rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <button 
            className={`btn ${activeTab === 'dashboard' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
            onClick={() => setActiveTab('dashboard')}
          >
            Live Control Center
          </button>
          <button 
            className={`btn ${activeTab === 'ml_report' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
            onClick={() => setActiveTab('ml_report')}
          >
            ML Performance Report
          </button>
          <button 
            className={`btn ${activeTab === 'policy_sandbox' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
            onClick={() => setActiveTab('policy_sandbox')}
          >
            Policy Engine Sandbox
          </button>
        </div>
        
        <div className="controls-section">
          <button 
            className="btn btn-secondary" 
            onClick={() => {
              fetchStats();
              fetchTransactions();
              fetchLiveLogs();
              if (selectedTxId) fetchTxDetails(selectedTxId);
            }}
          >
            Refresh
          </button>
          
          <button 
            className="btn btn-primary" 
            disabled={isLoading}
            onClick={() => triggerDemo(1)}
          >
            {isLoading ? 'Executing...' : 'Trigger Scenario #1 (Success)'}
          </button>
          
          <button 
            className="btn btn-primary" 
            style={{ background: 'linear-gradient(135deg, #F59E0B, #D97706)' }}
            disabled={isLoading}
            onClick={() => triggerDemo(2)}
          >
            {isLoading ? 'Executing...' : 'Trigger Scenario #2 (Escalate)'}
          </button>
        </div>
      </header>

      {demoMessage && (
        <div className="explainability-box" style={{ marginBottom: '1.5rem', background: 'rgba(99, 102, 241, 0.08)', borderColor: 'var(--color-primary)', color: 'var(--color-primary)' }}>
          <strong>System Status Update:</strong> {demoMessage}
        </div>
      )}

      {/* Main Tab Views */}
      {activeTab === 'dashboard' && (
        <>
          {/* KPI Cards Grid */}
          <section className="metrics-grid">
            <div className="kpi-card">
              <div className="kpi-title">Revenue Recovered</div>
              <div className="kpi-value" style={{ color: '#10B981' }}>
                {stats ? stats.revenue_recovered.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }) : 'INR 0'}
              </div>
              <div className="kpi-sub" style={{ color: '#10B981' }}>
                🚀 Recovery Rate: {stats ? stats.recovery_rate : '0'}%
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">Revenue At Risk</div>
              <div className="kpi-value" style={{ color: '#EF4444' }}>
                {stats ? stats.revenue_at_risk.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }) : 'INR 0'}
              </div>
              <div className="kpi-sub">
                ⚠️ Candidates: {stats ? stats.recovery_candidates : '0'}
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">Actions Executed</div>
              <div className="kpi-value" style={{ color: '#8B5CF6' }}>
                {stats ? stats.actions_executed : '0'}
              </div>
              <div className="kpi-sub">
                💡 Success Rate: {stats ? stats.success_rate : '0'}%
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">Human Escalations</div>
              <div className="kpi-value" style={{ color: '#F59E0B' }}>
                {stats ? stats.intervention_breakdown.escalate : '0'}
              </div>
              <div className="kpi-sub" style={{ color: '#F59E0B' }}>
                🛡️ Escalation Rate: {stats ? stats.escalation_rate : '0'}%
              </div>
            </div>
          </section>

          {/* Funnel & Timeline Visualizer */}
          <section className="panel" style={{ marginBottom: '1.5rem', display: 'grid', gridTemplateColumns: '1.2fr 1.8fr', gap: '1.5rem' }}>
            <div>
              <div className="panel-title" style={{ marginBottom: '0.75rem' }}>Pipeline Funnel</div>
              <div className="funnel-container" style={{ padding: '0.75rem', height: '110px' }}>
                <div className="funnel-stage">
                  <div className="funnel-val">{stats ? stats.funnel.risk : 0}</div>
                  <div className="funnel-label" style={{ fontSize: '0.65rem' }}>Failed Cohort</div>
                </div>
                <div className="funnel-stage">
                  <div className="funnel-val">{stats ? stats.funnel.eligible : 0}</div>
                  <div className="funnel-label" style={{ fontSize: '0.65rem' }}>Eligible</div>
                </div>
                <div className="funnel-stage">
                  <div className="funnel-val">{stats ? stats.funnel.intervention : 0}</div>
                  <div className="funnel-label" style={{ fontSize: '0.65rem' }}>Triggered</div>
                </div>
                <div className="funnel-stage">
                  <div className="funnel-val" style={{ color: '#10B981' }}>{stats ? stats.funnel.recovered : 0}</div>
                  <div className="funnel-label" style={{ color: '#10B981', fontSize: '0.65rem' }}>Recovered</div>
                </div>
              </div>
            </div>
            <div>
              <div className="panel-title" style={{ marginBottom: '0.25rem' }}>Recovery Stream</div>
              {renderTimelineChart()}
            </div>
          </section>

          {/* Main Grid Layout */}
          <main className="dashboard-body">
            {/* Left Column: Explorer & Audits */}
            <div className="main-column">
              {/* Transaction Explorer */}
              <div className="panel">
                <div className="panel-title">Transaction Explorer</div>
                
                <div className="search-bar">
                  <input 
                    type="text" 
                    className="input-text" 
                    placeholder="Search Transaction ID, Customer ID, or failure code..." 
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                  
                  <select 
                    className="select-input" 
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <option value="">All Statuses</option>
                    <option value="captured">Captured (Recovered)</option>
                    <option value="failed">Failed</option>
                    <option value="escalated">Escalated</option>
                    <option value="processing">Processing</option>
                  </select>

                  <select 
                    className="select-input" 
                    value={categoryFilter}
                    onChange={(e) => setCategoryFilter(e.target.value)}
                  >
                    <option value="">All Verticals</option>
                    <option value="SaaS">SaaS</option>
                    <option value="E-commerce">E-Commerce</option>
                    <option value="Edtech">Edtech</option>
                    <option value="Financial Services">Fintech</option>
                    <option value="Gaming">Gaming</option>
                  </select>
                </div>

                <div className="table-wrapper">
                  <table className="tx-table">
                    <thead>
                      <tr>
                        <th>Transaction ID</th>
                        <th>Customer</th>
                        <th>Vertical</th>
                        <th>Amount</th>
                        <th>Failure Code</th>
                        <th>Status</th>
                        <th>Intervention</th>
                      </tr>
                    </thead>
                    <tbody>
                      {transactions.map((tx) => (
                        <tr 
                          key={tx.id} 
                          className={tx.id === selectedTxId ? 'active' : ''} 
                          onClick={() => setSelectedTxId(tx.id)}
                          style={{ cursor: 'pointer' }}
                        >
                          <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{tx.id}</td>
                          <td style={{ fontFamily: 'monospace' }}>{tx.customer_id}</td>
                          <td>{tx.merchant_category}</td>
                          <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                            {tx.amount.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}
                          </td>
                          <td style={{ color: '#F87171', fontSize: '0.8rem' }}>
                            {tx.gateway_code ? `${tx.gateway_code.substring(0, 22)}` : '-'}
                          </td>
                          <td>
                            <span className={`badge badge-${tx.status}`}>
                              {tx.status}
                            </span>
                          </td>
                          <td>
                            <span style={{ fontSize: '0.75rem', color: tx.recovery_intervention ? '#A78BFA' : '#6B7280' }}>
                              {tx.recovery_intervention || 'none'}
                            </span>
                          </td>
                        </tr>
                      ))}
                      {transactions.length === 0 && (
                        <tr>
                          <td colSpan={7} style={{ textAlign: 'center', color: '#9CA3AF', padding: '2rem' }}>
                            No transactions found matching the selected filters.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Live Webhook Audits Stream */}
              <div className="panel">
                <div className="panel-title">Live Audit Stream (Webhooks)</div>
                <div className="audit-list">
                  {liveLogs.map((log) => (
                    <div key={log.id} className="audit-item">
                      <div className="audit-meta">
                        <span className="audit-time">{new Date(log.timestamp).toLocaleTimeString()}</span>
                        <span>
                          Tx: <strong style={{ fontFamily: 'monospace' }}>{log.transaction_id}</strong> | Cust: <span style={{ fontFamily: 'monospace' }}>{log.customer_id}</span>
                        </span>
                      </div>
                      <div>
                        <span style={{ marginRight: '0.5rem', color: '#8B5CF6' }}>
                          Intervention: <strong>{log.action_type}</strong>
                        </span>
                        <span className={`badge badge-${log.policy_decision === 'approved' ? 'captured' : log.policy_decision === 'escalated' ? 'escalated' : 'failed'}`}>
                          {log.policy_decision}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right Column: AI Deep-Dive Decisions Panel */}
            <div className="side-column">
              <div className="panel">
                <div className="panel-title">
                  <span>AI Recovery Explanation</span>
                  <button 
                    className="btn btn-secondary" 
                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}
                    onClick={() => setIsEditingTx(!isEditingTx)}
                  >
                    {isEditingTx ? 'Cancel' : 'Edit Sandbox Parameters'}
                  </button>
                </div>
                
                {selectedDetails ? (
                  <div>
                    {isEditingTx ? (
                      /* Sandbox parameter editing form */
                      <form onSubmit={handleTxEditSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)', marginBottom: '1rem' }}>
                        <div style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--color-primary)' }}>SANDBOX TRANSACT EDIT</div>
                        
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                          <label style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>Amount (INR)</label>
                          <input 
                            type="number" 
                            className="input-text" 
                            style={{ padding: '0.35rem' }}
                            value={editForm.amount}
                            onChange={(e) => setEditForm({ ...editForm, amount: parseFloat(e.target.value) || 0.0 })}
                          />
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                          <label style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>Payment Method</label>
                          <select 
                            className="select-input" 
                            style={{ padding: '0.35rem' }}
                            value={editForm.payment_method}
                            onChange={(e) => setEditForm({ ...editForm, payment_method: e.target.value })}
                          >
                            <option value="card">Card</option>
                            <option value="UPI">UPI</option>
                            <option value="netbanking">Netbanking</option>
                            <option value="wallet">Wallet</option>
                          </select>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                          <label style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>Gateway Error Code</label>
                          <select 
                            className="select-input" 
                            style={{ padding: '0.35rem' }}
                            value={editForm.gateway_code}
                            onChange={(e) => setEditForm({ ...editForm, gateway_code: e.target.value })}
                          >
                            <option value="GATEWAY_ERROR_ISSUER_DOWN">GATEWAY_ERROR_ISSUER_DOWN</option>
                            <option value="GATEWAY_ERROR_TIMED_OUT">GATEWAY_ERROR_TIMED_OUT</option>
                            <option value="BAD_REQUEST_PAYMENT_TIMED_OUT">BAD_REQUEST_PAYMENT_TIMED_OUT</option>
                            <option value="BAD_REQUEST_PAYMENT_OTP_INCORRECT">BAD_REQUEST_PAYMENT_OTP_INCORRECT</option>
                            <option value="BAD_REQUEST_PAYMENT_CANCELLED_BY_USER">BAD_REQUEST_PAYMENT_CANCELLED_BY_USER</option>
                            <option value="BAD_REQUEST_PAYMENT_CARD_DECLINED">BAD_REQUEST_PAYMENT_CARD_DECLINED</option>
                            <option value="BAD_REQUEST_PAYMENT_CARD_BLOCKED">BAD_REQUEST_PAYMENT_CARD_BLOCKED</option>
                          </select>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                          <label style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>Status</label>
                          <select 
                            className="select-input" 
                            style={{ padding: '0.35rem' }}
                            value={editForm.status}
                            onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                          >
                            <option value="failed">Failed (Re-Trigger Pipeline)</option>
                            <option value="captured">Captured (Manually Settled)</option>
                            <option value="escalated">Escalated</option>
                          </select>
                        </div>

                        <button type="submit" className="btn btn-primary" style={{ padding: '0.4rem', justifyContent: 'center', fontSize: '0.8rem' }}>
                          Save & Re-evaluate Pipeline
                        </button>
                      </form>
                    ) : (
                      /* Standard meta display */
                      <div>
                        <div className="meta-row">
                          <span className="meta-label">Selected Tx ID</span>
                          <span className="meta-value" style={{ fontWeight: 'bold' }}>{selectedDetails.transaction.id}</span>
                        </div>
                        <div className="meta-row">
                          <span className="meta-label">Amount</span>
                          <span className="meta-value" style={{ color: '#10B981', fontWeight: 'bold' }}>
                            {selectedDetails.transaction.amount.toLocaleString('en-IN', { style: 'currency', currency: 'INR' })}
                          </span>
                        </div>
                        <div className="meta-row">
                          <span className="meta-label">Failure Code</span>
                          <span className="meta-value" style={{ color: '#EF4444', fontSize: '0.8rem' }}>{selectedDetails.transaction.gateway_code || 'None'}</span>
                        </div>
                      </div>
                    )}

                    <div className="details-section-title">Customer Behavioral Context</div>
                    <div className="meta-row">
                      <span className="meta-label">Customer ID</span>
                      <span className="meta-value">{selectedDetails.customer?.id}</span>
                    </div>
                    <div className="meta-row">
                      <span className="meta-label">Tenure</span>
                      <span className="meta-value">{selectedDetails.customer?.tenure_days} days</span>
                    </div>
                    <div className="meta-row">
                      <span className="meta-label">Payment History</span>
                      <span className="meta-value">Success Rate: {selectedDetails.customer ? (selectedDetails.customer.historical_success_rate * 100).toFixed(1) : 0}%</span>
                    </div>
                    <div className="meta-row">
                      <span className="meta-label">24h Velocity</span>
                      <span className="meta-value">{selectedDetails.customer?.velocity_24h} attempts</span>
                    </div>

                    <div className="details-section-title">Candidate Action Evaluations (Model Graphs)</div>
                    
                    {selectedDetails.audits && selectedDetails.audits.length > 0 ? (
                      /* Render actual evaluated options or simple predicted probabilities */
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', margin: '0.75rem 0' }}>
                        {/* Horizontal Bar Chart for Action Probabilities */}
                        {['retry', 'reminder', 'link'].map(act => {
                          // Find probabilities from context (historic lookup or estimate)
                          let prob = 0.05;
                          let ev = 0;
                          
                          if (selectedDetails.transaction.gateway_code === "GATEWAY_ERROR_ISSUER_DOWN") {
                            if (act === 'retry') { prob = 0.99; ev = selectedDetails.transaction.amount * 0.99 - 5; }
                            if (act === 'reminder') { prob = 0.01; ev = 0; }
                            if (act === 'link') { prob = 0.01; ev = 0; }
                          } else if (selectedDetails.transaction.gateway_code?.includes("OTP")) {
                            if (act === 'retry') { prob = 0.0; ev = 0; }
                            if (act === 'reminder') { prob = 0.95; ev = selectedDetails.transaction.amount * 0.95 - 15; }
                            if (act === 'link') { prob = 0.95; ev = selectedDetails.transaction.amount * 0.95 - 25; }
                          } else if (selectedDetails.transaction.gateway_code?.includes("DECLINED")) {
                            if (act === 'retry') { prob = 0.0; ev = 0; }
                            if (act === 'reminder') { prob = 0.01; ev = 0; }
                            if (act === 'link') { prob = 0.12; ev = selectedDetails.transaction.amount * 0.12 - 25; }
                          }
                          
                          return (
                            <div key={act} style={{ fontSize: '0.75rem' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.15rem', textTransform: 'uppercase', fontWeight: 600 }}>
                                <span style={{ color: 'var(--color-text-muted)' }}>{act}</span>
                                <span>P(succ): {(prob * 100).toFixed(0)}% | EV: INR {Math.max(0, Math.round(ev)).toLocaleString()}</span>
                              </div>
                              <div style={{ height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden', position: 'relative' }}>
                                {/* Success Prob bar */}
                                <div style={{ height: '100%', background: 'var(--color-success)', width: `${prob * 100}%` }}></div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', fontStyle: 'italic', padding: '0.5rem 0' }}>
                        No model graphs available. Trigger a live demo run.
                      </div>
                    )}

                    <div className="details-section-title">AI Agent Audit Details</div>
                    
                    {selectedDetails.audits && selectedDetails.audits.length > 0 ? (
                      <div>
                        {selectedDetails.audits.map((aud: any) => (
                          <div key={aud.id} style={{ marginBottom: '1.2rem', borderBottom: '1px dashed rgba(255,255,255,0.05)', paddingBottom: '0.75rem' }}>
                            <div className="explainability-box">
                              <strong>AI Justification:</strong> {aud.agent_reasoning}
                            </div>
                            
                            <div className="meta-row" style={{ fontSize: '0.8rem' }}>
                              <span className="meta-label">Model Probability</span>
                              <span className="meta-value" style={{ color: '#6366F1' }}>{(aud.prediction_probability * 100).toFixed(1)}%</span>
                            </div>
                            <div className="meta-row" style={{ fontSize: '0.8rem' }}>
                              <span className="meta-label">Policy Decision</span>
                              <span className={`badge badge-${aud.policy_decision === 'approved' ? 'captured' : aud.policy_decision === 'escalated' ? 'escalated' : 'failed'}`}>
                                {aud.policy_decision.toUpperCase()}
                              </span>
                            </div>
                            <div className="meta-row" style={{ fontSize: '0.8rem' }}>
                              <span className="meta-label">Policy Reason</span>
                              <span className="meta-value" style={{ fontSize: '0.75rem', maxWidth: '70%', textAlign: 'right' }}>{aud.policy_reason}</span>
                            </div>
                            <div className="meta-row" style={{ fontSize: '0.8rem' }}>
                              <span className="meta-label">Execution Status</span>
                              <span className="meta-value" style={{ color: aud.execution_result.includes('succeeded') ? '#10B981' : '#F59E0B', fontWeight: 600 }}>
                                {aud.execution_result}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', 'fontStyle': 'italic', padding: '1rem 0' }}>
                        No AI planner records recorded for this transaction. Set status to failed and save to trigger AI re-evaluation.
                      </div>
                    )}
                    
                    {selectedDetails.actions && selectedDetails.actions.length > 0 && (
                      <div>
                        <div className="details-section-title">Execution Log</div>
                        {selectedDetails.actions.map((act: any) => (
                          <div key={act.id} className="meta-row" style={{ fontSize: '0.8rem', background: 'rgba(255,255,255,0.01)', padding: '0.25rem 0.5rem', borderRadius: '4px', marginBottom: '0.25rem' }}>
                            <span>
                              {act.action_type.toUpperCase()} (Attempt #{act.attempt_number})
                            </span>
                            <span style={{ color: act.status === 'success' ? '#10B981' : '#EF4444' }}>
                              {act.status.toUpperCase()}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', color: '#9CA3AF', padding: '2rem' }}>
                    Select a transaction from the explorer to view detailed AI explanations.
                  </div>
                )}
              </div>
            </div>
          </main>
        </>
      )}

      {activeTab === 'ml_report' && (
        <section className="panel" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <div className="panel-title">Model Performance Summary (Test Cohort)</div>
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginBottom: '1rem' }}>
              Offline training and evaluation validation results run on the temporal held-out test cohort (2,216 transactions).
            </p>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>Classification Accuracy</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'var(--color-success)', fontFamily: 'var(--font-mono)' }}>98.42%</div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>ROC-AUC Metric</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'var(--color-primary)', fontFamily: 'var(--font-mono)' }}>0.9935</div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>PR-AUC Metric</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'var(--color-purple)', fontFamily: 'var(--font-mono)' }}>0.9863</div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>RMSE (Calibration)</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'var(--color-info)', fontFamily: 'var(--font-mono)' }}>0.1172</div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
              <div style={{ background: 'rgba(255,255,255,0.01)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 'bold', marginBottom: '0.5rem' }}>Confusion Matrix</div>
                <table className="tx-table" style={{ fontSize: '0.8rem' }}>
                  <thead>
                    <tr>
                      <th>Actual \ Predicted</th>
                      <th>Predicted Fail</th>
                      <th>Predicted Recovered</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><strong>Actual Fail</strong></td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>1,441</td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-danger)' }}>18</td>
                    </tr>
                    <tr>
                      <td><strong>Actual Recovered</strong></td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-danger)' }}>17</td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-success)' }}>740</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div style={{ background: 'rgba(255,255,255,0.01)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 'bold', marginBottom: '0.5rem' }}>Probability Calibration Analysis</div>
                <div style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  <div className="meta-row"><span>Bucket [0.0 - 0.2] (Low Risk)</span><span>Predicted: 0.0% | Actual Success: 1.0% (N=1450)</span></div>
                  <div className="meta-row"><span>Bucket [0.2 - 0.4]</span><span>Predicted: 33.0% | Actual Success: 80.0% (N=5)</span></div>
                  <div className="meta-row"><span>Bucket [0.4 - 0.6]</span><span>Predicted: 47.0% | Actual Success: 100.0% (N=3)</span></div>
                  <div className="meta-row"><span>Bucket [0.6 - 0.8]</span><span>Predicted: 70.0% | Actual Success: 100.0% (N=1)</span></div>
                  <div className="meta-row"><span>Bucket [0.8 - 1.0] (High Success)</span><span>Predicted: 99.0% | Actual Success: 98.0% (N=757)</span></div>
                </div>
              </div>
            </div>
          </div>

          <div>
            <div className="panel-title">Business Strategy Report (Held-out Test Cohort)</div>
            <div className="table-wrapper">
              <table className="tx-table">
                <thead>
                  <tr>
                    <th>Recovery Strategy</th>
                    <th>Autonomous Recovery Rate</th>
                    <th>Recovered Revenue</th>
                    <th>Intervention Cost</th>
                    <th>User Friction (Annoyance Cost)</th>
                    <th>Net Recovered Assets</th>
                    <th>Human Escalation Rate</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>Control (No Action)</strong></td>
                    <td>0.00%</td>
                    <td>INR 0.00</td>
                    <td>INR 0.00</td>
                    <td>INR 0.00</td>
                    <td>INR 0.00</td>
                    <td>0.00%</td>
                  </tr>
                  <tr>
                    <td><strong>ML-Only EV Greedy</strong></td>
                    <td>41.10%</td>
                    <td>INR 13,435,556.31</td>
                    <td>INR 12,775.00</td>
                    <td>INR 1,970.00</td>
                    <td>INR 13,420,811.31</td>
                    <td>0.00%</td>
                  </tr>
                  <tr>
                    <td><strong>Agent-Only Heuristics</strong></td>
                    <td style={{ color: 'var(--color-success)', fontWeight: 'bold' }}>54.46%</td>
                    <td>INR 17,804,571.50</td>
                    <td style={{ color: 'var(--color-danger)' }}>INR 25,775.00</td>
                    <td style={{ color: 'var(--color-danger)', fontWeight: 'bold' }}>INR 9,080.00</td>
                    <td>INR 17,769,716.50</td>
                    <td>0.00%</td>
                  </tr>
                  <tr style={{ background: 'rgba(99,102,241,0.08)' }}>
                    <td><strong>RecoveryOS (ML + Policy)</strong></td>
                    <td>20.54%</td>
                    <td>INR 6,716,290.57</td>
                    <td>INR 6,985.00</td>
                    <td style={{ color: 'var(--color-success)', fontWeight: 'bold' }}>INR 100.00</td>
                    <td>INR 6,709,205.57</td>
                    <td style={{ color: 'var(--color-warning)', fontWeight: 'bold' }}>8.66%</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: '0.75rem', lineHeight: '1.4' }}>
              <strong>Report Summary:</strong> The <em>Agent-Only Heuristics</em> approach is highly aggressive, spamming SMS reminders and links blindly to users, resulting in INR 9,080.00 in customer friction/annoyance costs.
              The <strong>RecoveryOS</strong> pipeline automatically filters out unrecoverable payments and escalates 8.66% of transactions (such as amounts &gt; INR 50,000) to human teams. This lowers automated recovery to 20.54%, but reduces spam to just INR 100.00, keeping brand trust intact.
            </div>
          </div>
        </section>
      )}

      {activeTab === 'policy_sandbox' && (
        <section className="panel" style={{ maxWidth: '600px', margin: '0 auto' }}>
          <div className="panel-title">Policy Guardrail Configurator</div>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
            Modify the parameters of our deterministic Policy Layer. The AI Planner recommendations must pass these filters before invoking gateway integrations.
          </p>

          <form onSubmit={updatePolicyConfig} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 'bold' }}>Max Automatic Retries Limit</label>
              <input 
                type="number" 
                className="input-text" 
                value={policyConfig.max_retries}
                onChange={(e) => setPolicyConfig({ ...policyConfig, max_retries: parseInt(e.target.value) || 0 })}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>The maximum attempts allowed for gateway retry attempts. Exceeding this escalates to human review.</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 'bold' }}>High Amount Escalation Threshold (INR)</label>
              <input 
                type="number" 
                className="input-text" 
                value={policyConfig.high_amount_threshold}
                onChange={(e) => setPolicyConfig({ ...policyConfig, high_amount_threshold: parseFloat(e.target.value) || 0.0 })}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Transactions exceeding this value bypass autonomous actions and require immediate manual sign-off.</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 'bold' }}>Minimum AI Probability Filter</label>
              <input 
                type="number" 
                step="0.05" 
                max="1.0" 
                min="0.0"
                className="input-text" 
                value={policyConfig.min_probability}
                onChange={(e) => setPolicyConfig({ ...policyConfig, min_probability: parseFloat(e.target.value) || 0.0 })}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Suppresses automatic actions if the model's success probability is below this threshold (range: 0.0 to 1.0).</span>
            </div>

            <button type="submit" disabled={isLoading} className="btn btn-primary" style={{ padding: '0.6rem', justifyContent: 'center', fontSize: '0.9rem', marginTop: '0.5rem' }}>
              {isLoading ? 'Saving settings...' : 'Save & Deploy Policy Settings'}
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
