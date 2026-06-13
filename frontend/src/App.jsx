import { useState, useEffect, useCallback } from "react";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from "recharts";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

// ── Helpers ───────────────────────────────────────────────────────────────────

const TIER_COLORS = {
  hot: "#ef4444",
  warm: "#f97316",
  cold: "#3b82f6",
  disqualified: "#6b7280",
};

const TIER_EMOJI = { hot: "🔥", warm: "🌤️", cold: "❄️", disqualified: "✖️" };

async function apiFetch(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

// ── Score ring ─────────────────────────────────────────────────────────────────

function ScoreRing({ score, tier }) {
  const pct = Math.round(score * 100);
  const r = 40;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  const color = TIER_COLORS[tier] || "#6b7280";
  return (
    <div className="score-ring">
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#1e293b" strokeWidth="10" />
        <circle
          cx="50" cy="50" r={r} fill="none"
          stroke={color} strokeWidth="10"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
          style={{ transition: "stroke-dasharray 0.6s ease" }}
        />
        <text x="50" y="46" textAnchor="middle" fill="#f1f5f9" fontSize="18" fontWeight="bold">{pct}</text>
        <text x="50" y="62" textAnchor="middle" fill={color} fontSize="10">{tier?.toUpperCase()}</text>
      </svg>
    </div>
  );
}

// ── Stat card ──────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, accent }) {
  return (
    <div className="stat-card" style={{ "--accent": accent }}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

// ── Lead row ───────────────────────────────────────────────────────────────────

function LeadRow({ lead, onClick }) {
  const score = lead.score != null ? Math.round(lead.score * 100) : "–";
  const tier = lead.tier || "–";
  return (
    <tr className="lead-row" onClick={() => onClick(lead)}>
      <td>
        <div className="lead-email">{lead.email}</div>
        <div className="lead-company">{lead.company || "–"}</div>
      </td>
      <td>
        <span className="tier-badge" style={{ "--tc": TIER_COLORS[tier] }}>
          {TIER_EMOJI[tier]} {tier}
        </span>
      </td>
      <td>
        <div className="score-bar-wrap">
          <div className="score-bar" style={{ width: `${score}%`, background: TIER_COLORS[tier] }} />
          <span>{score}</span>
        </div>
      </td>
      <td>{lead.rep_name || "Unassigned"}</td>
      <td>
        <span className={`status-dot status-${lead.assignment_status}`} />
        {lead.assignment_status || "–"}
      </td>
      <td className="ts">{new Date(lead.created_at).toLocaleString()}</td>
    </tr>
  );
}

// ── Lead detail panel ──────────────────────────────────────────────────────────

function LeadDetail({ lead, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch(`/leads/${lead.lead_id}/score`)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [lead.lead_id]);

  return (
    <div className="detail-overlay" onClick={onClose}>
      <div className="detail-panel" onClick={e => e.stopPropagation()}>
        <button className="close-btn" onClick={onClose}>✕</button>
        <h2>{lead.email}</h2>
        <p className="detail-company">{lead.company || "No company"}</p>

        {loading ? (
          <div className="loading-spinner" />
        ) : detail ? (
          <>
            <div className="detail-score-wrap">
              <ScoreRing score={detail.score} tier={detail.tier} />
              <div className="detail-meta">
                <div>Model: <strong>{detail.model_name} v{detail.model_version}</strong></div>
                <div>Source: <strong>{lead.source}</strong></div>
                <div>Rep: <strong>{lead.rep_name || "Unassigned"}</strong></div>
                <div>Status: <strong>{lead.assignment_status || "–"}</strong></div>
              </div>
            </div>

            <h3>Top SHAP Factors</h3>
            <div className="shap-chart">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  layout="vertical"
                  data={detail.top_factors}
                  margin={{ left: 120, right: 20 }}
                >
                  <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <YAxis
                    dataKey="feature" type="category"
                    tick={{ fill: "#94a3b8", fontSize: 11 }}
                    width={120}
                  />
                  <Tooltip
                    contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
                    formatter={(v) => [v.toFixed(4), "SHAP"]}
                  />
                  <Bar dataKey="shap_value" radius={[0, 4, 4, 0]}>
                    {detail.top_factors.map((f, i) => (
                      <Cell key={i} fill={f.shap_value >= 0 ? "#22c55e" : "#ef4444"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        ) : (
          <p className="no-data">Score details unavailable</p>
        )}
      </div>
    </div>
  );
}

// ── Submit form ────────────────────────────────────────────────────────────────

function SubmitForm({ onSubmitted }) {
  const [form, setForm] = useState({ email: "", company: "", website: "", source: "web" });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const submit = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/leads/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, time_on_site_s: 90, pages_visited: 3 }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Submission failed");
      }
      const data = await res.json();
      setResult(data);
      onSubmitted?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (result) return (
    <div className="submit-result">
      <ScoreRing score={result.score} tier={result.tier} />
      <h3>{result.message}</h3>
      <div className="factors">
        {result.top_factors.slice(0, 3).map((f, i) => (
          <div key={i} className={`factor factor-${f.direction}`}>
            {f.feature}: {f.direction === "positive" ? "↑" : "↓"}
          </div>
        ))}
      </div>
      <button className="btn btn-ghost" onClick={() => { setResult(null); setForm({ email: "", company: "", website: "", source: "web" }); }}>
        Submit another
      </button>
    </div>
  );

  return (
    <div className="submit-form">
      <h3>Test Lead Submission</h3>
      <input placeholder="Email *" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
      <input placeholder="Company" value={form.company} onChange={e => setForm(f => ({ ...f, company: e.target.value }))} />
      <input placeholder="Website" value={form.website} onChange={e => setForm(f => ({ ...f, website: e.target.value }))} />
      <select value={form.source} onChange={e => setForm(f => ({ ...f, source: e.target.value }))}>
        {["organic","referral","email","paid","social","direct","web"].map(s => (
          <option key={s}>{s}</option>
        ))}
      </select>
      {error && <div className="form-error">{error}</div>}
      <button className="btn btn-primary" onClick={submit} disabled={loading || !form.email}>
        {loading ? "Scoring…" : "Submit & Score →"}
      </button>
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────────────────────

export default function App() {
  const [stats, setStats] = useState(null);
  const [leads, setLeads] = useState([]);
  const [drift, setDrift] = useState(null);
  const [selectedLead, setSelectedLead] = useState(null);
  const [tierFilter, setTierFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("dashboard");

  const loadData = useCallback(async () => {
    try {
      const [s, l, d] = await Promise.all([
        apiFetch("/dashboard/stats"),
        apiFetch(`/dashboard/leads?limit=100${tierFilter !== "all" ? `&tier=${tierFilter}` : ""}`),
        apiFetch("/dashboard/drift"),
      ]);
      setStats(s);
      setLeads(l);
      setDrift(d);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [tierFilter]);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => {
    const t = setInterval(loadData, 30000);
    return () => clearInterval(t);
  }, [loadData]);

  const tierPieData = stats ? [
    { name: "Hot", value: stats.hot_count, fill: TIER_COLORS.hot },
    { name: "Warm", value: stats.warm_count, fill: TIER_COLORS.warm },
    { name: "Cold", value: stats.cold_count, fill: TIER_COLORS.cold },
    { name: "DQ", value: stats.disqualified_count, fill: TIER_COLORS.disqualified },
  ] : [];

  return (
    <>
      <style>{CSS}</style>
      <div className="app">
        <nav className="navbar">
          <div className="nav-brand">
            <span className="brand-icon">⚡</span>
            <span className="brand-name">SmartIntake</span>
            <span className="brand-tag">ML Lead Triage</span>
          </div>
          <div className="nav-tabs">
            {["dashboard", "leads", "submit"].map(t => (
              <button key={t} className={`nav-tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
          <div className="nav-status">
            {drift?.drift_detected ? (
              <span className="drift-alert">⚠ Drift Detected PSI {drift.latest_psi?.toFixed(3)}</span>
            ) : (
              <span className="drift-ok">✓ Model Stable</span>
            )}
          </div>
        </nav>

        <main className="main">
          {/* ─── Dashboard tab ─────────────────────────────────────────── */}
          {tab === "dashboard" && (
            <div className="dashboard">
              {loading ? (
                <div className="loading-full"><div className="loading-spinner" /></div>
              ) : (
                <>
                  <div className="stats-grid">
                    <StatCard label="Total Leads" value={stats?.total_leads ?? "–"} accent="#6366f1" />
                    <StatCard label="Hot Leads 🔥" value={stats?.hot_count ?? "–"} accent="#ef4444" />
                    <StatCard label="Avg Score" value={stats ? `${Math.round(stats.avg_score * 100)}` : "–"} sub="out of 100" accent="#22c55e" />
                    <StatCard label="Today" value={stats?.leads_today ?? "–"} sub="new leads" accent="#f97316" />
                    <StatCard label="Conversion" value={stats ? `${(stats.conversion_rate * 100).toFixed(1)}%` : "–"} accent="#06b6d4" />
                    <StatCard
                      label="Drift PSI"
                      value={drift?.latest_psi?.toFixed(3) ?? "–"}
                      sub={drift?.drift_detected ? "⚠ Drifted" : "✓ Stable"}
                      accent={drift?.drift_detected ? "#ef4444" : "#22c55e"}
                    />
                  </div>

                  <div className="charts-row">
                    <div className="chart-card">
                      <h3>Tier Distribution</h3>
                      <ResponsiveContainer width="100%" height={220}>
                        <PieChart>
                          <Pie data={tierPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                            {tierPieData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                          </Pie>
                          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>

                    <div className="chart-card">
                      <h3>Feature Drift (per column)</h3>
                      {drift?.feature_drift ? (
                        <ResponsiveContainer width="100%" height={220}>
                          <BarChart data={Object.entries(drift.feature_drift).map(([k, v]) => ({ name: k.replace(/_/g, " "), psi: v }))}>
                            <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10 }} angle={-30} textAnchor="end" height={50} />
                            <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} />
                            <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
                            <Bar dataKey="psi" radius={[4, 4, 0, 0]}>
                              {Object.values(drift.feature_drift).map((v, i) => (
                                <Cell key={i} fill={v > 0.20 ? "#ef4444" : v > 0.10 ? "#f97316" : "#22c55e"} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      ) : <div className="no-data">No drift data yet</div>}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ─── Leads tab ─────────────────────────────────────────────── */}
          {tab === "leads" && (
            <div className="leads-tab">
              <div className="leads-toolbar">
                <h2>Lead Pipeline</h2>
                <div className="filter-tabs">
                  {["all", "hot", "warm", "cold", "disqualified"].map(t => (
                    <button key={t} className={`filter-btn ${tierFilter === t ? "active" : ""}`}
                      style={tierFilter === t && t !== "all" ? { "--fc": TIER_COLORS[t] } : {}}
                      onClick={() => setTierFilter(t)}>
                      {t !== "all" ? TIER_EMOJI[t] : "🔍"} {t}
                    </button>
                  ))}
                </div>
                <button className="btn btn-ghost" onClick={loadData}>↺ Refresh</button>
              </div>

              <div className="table-wrap">
                <table className="leads-table">
                  <thead>
                    <tr>
                      <th>Lead</th><th>Tier</th><th>Score</th><th>Rep</th><th>Status</th><th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leads.length === 0 ? (
                      <tr><td colSpan={6} className="empty">No leads yet — submit one!</td></tr>
                    ) : leads.map(l => (
                      <LeadRow key={l.lead_id} lead={l} onClick={setSelectedLead} />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ─── Submit tab ─────────────────────────────────────────────── */}
          {tab === "submit" && (
            <div className="submit-tab">
              <SubmitForm onSubmitted={() => { setTimeout(loadData, 1000); }} />
            </div>
          )}
        </main>

        {selectedLead && (
          <LeadDetail lead={selectedLead} onClose={() => setSelectedLead(null)} />
        )}
      </div>
    </>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@400;500;600;700&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #020617;
    --surface: #0f172a;
    --surface2: #1e293b;
    --border: #334155;
    --text: #f1f5f9;
    --muted: #94a3b8;
    --accent: #6366f1;
  }

  body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; }

  .app { min-height: 100vh; display: flex; flex-direction: column; }

  /* Nav */
  .navbar {
    display: flex; align-items: center; gap: 24px; padding: 12px 24px;
    background: var(--surface); border-bottom: 1px solid var(--border);
    position: sticky; top: 0; z-index: 100;
  }
  .nav-brand { display: flex; align-items: center; gap: 8px; }
  .brand-icon { font-size: 20px; }
  .brand-name { font-weight: 700; font-size: 18px; letter-spacing: -0.5px; }
  .brand-tag { font-size: 11px; color: var(--muted); background: var(--surface2); padding: 2px 8px; border-radius: 20px; }
  .nav-tabs { display: flex; gap: 4px; margin-left: 16px; }
  .nav-tab {
    padding: 6px 16px; border-radius: 6px; border: none; background: transparent;
    color: var(--muted); cursor: pointer; font-size: 14px; font-weight: 500;
    transition: all .15s;
  }
  .nav-tab.active, .nav-tab:hover { background: var(--surface2); color: var(--text); }
  .nav-tab.active { color: #a5b4fc; }
  .nav-status { margin-left: auto; font-size: 13px; }
  .drift-alert { color: #fbbf24; background: #451a034d; padding: 4px 10px; border-radius: 20px; border: 1px solid #92400e; }
  .drift-ok { color: #4ade80; background: #052e164d; padding: 4px 10px; border-radius: 20px; border: 1px solid #166534; }

  /* Main */
  .main { flex: 1; padding: 24px; max-width: 1400px; margin: 0 auto; width: 100%; }

  /* Stats */
  .stats-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px;
  }
  .stat-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 20px; border-top: 3px solid var(--accent);
  }
  .stat-value { font-size: 32px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
  .stat-label { font-size: 12px; color: var(--muted); margin-top: 4px; text-transform: uppercase; letter-spacing: .5px; }
  .stat-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }

  /* Charts */
  .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .chart-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px;
  }
  .chart-card h3 { font-size: 14px; font-weight: 600; margin-bottom: 16px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }

  /* Table */
  .leads-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
  .leads-toolbar h2 { font-size: 20px; font-weight: 600; margin-right: auto; }
  .filter-tabs { display: flex; gap: 4px; }
  .filter-btn {
    padding: 5px 12px; border-radius: 6px; border: 1px solid var(--border);
    background: transparent; color: var(--muted); cursor: pointer; font-size: 12px;
    transition: all .15s; text-transform: capitalize;
  }
  .filter-btn.active { background: var(--fc, var(--accent)); color: white; border-color: transparent; }
  .filter-btn:hover:not(.active) { border-color: var(--text); color: var(--text); }

  .table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 12px; }
  .leads-table { width: 100%; border-collapse: collapse; }
  .leads-table th {
    text-align: left; padding: 10px 16px; font-size: 11px; text-transform: uppercase;
    letter-spacing: .5px; color: var(--muted); background: var(--surface); border-bottom: 1px solid var(--border);
  }
  .lead-row { cursor: pointer; transition: background .1s; }
  .lead-row:hover { background: var(--surface2); }
  .lead-row td { padding: 12px 16px; border-bottom: 1px solid #1e293b; font-size: 13px; }
  .lead-row:last-child td { border-bottom: none; }
  .lead-email { font-weight: 500; }
  .lead-company { color: var(--muted); font-size: 11px; margin-top: 2px; }
  .tier-badge {
    display: inline-block; padding: 2px 8px; border-radius: 20px;
    background: color-mix(in srgb, var(--tc) 20%, transparent);
    color: var(--tc); border: 1px solid color-mix(in srgb, var(--tc) 40%, transparent);
    font-size: 11px; font-weight: 600; text-transform: capitalize;
  }
  .score-bar-wrap { display: flex; align-items: center; gap: 8px; }
  .score-bar { height: 4px; border-radius: 2px; min-width: 2px; max-width: 80px; }
  .status-dot {
    display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 6px;
    background: var(--muted);
  }
  .status-dot.status-sent { background: #22c55e; }
  .status-dot.status-pending { background: #f59e0b; }
  .status-dot.status-converted { background: #6366f1; }
  .ts { color: var(--muted); font-family: 'JetBrains Mono', monospace; font-size: 11px; }
  .empty { text-align: center; padding: 40px; color: var(--muted); }

  /* Detail panel */
  .detail-overlay {
    position: fixed; inset: 0; background: #00000080; z-index: 200;
    display: flex; justify-content: flex-end; backdrop-filter: blur(4px);
  }
  .detail-panel {
    background: var(--surface); width: min(480px, 100vw); height: 100%; overflow-y: auto;
    padding: 32px; border-left: 1px solid var(--border); position: relative;
    animation: slideIn .2s ease;
  }
  @keyframes slideIn { from { transform: translateX(40px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
  .close-btn {
    position: absolute; top: 16px; right: 16px; background: var(--surface2); border: 1px solid var(--border);
    color: var(--muted); width: 30px; height: 30px; border-radius: 6px; cursor: pointer; font-size: 14px;
  }
  .detail-company { color: var(--muted); margin-bottom: 24px; font-size: 14px; }
  .detail-score-wrap { display: flex; gap: 20px; align-items: center; margin-bottom: 24px; }
  .detail-meta { font-size: 13px; line-height: 1.8; }
  .detail-meta div { color: var(--muted); }
  .detail-meta strong { color: var(--text); }
  h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .5px; color: var(--muted); margin: 16px 0 8px; }
  .shap-chart { margin-top: 8px; }

  /* Submit form */
  .submit-tab { max-width: 500px; margin: 0 auto; padding: 40px 0; }
  .submit-form { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 32px; }
  .submit-form h3 { margin-bottom: 20px; font-size: 18px; }
  .submit-form input, .submit-form select {
    width: 100%; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px;
    padding: 10px 14px; color: var(--text); font-size: 14px; margin-bottom: 12px; font-family: inherit;
  }
  .submit-form input::placeholder { color: var(--muted); }
  .submit-form select option { background: var(--surface2); }
  .form-error { color: #f87171; font-size: 13px; margin-bottom: 12px; }
  .submit-result { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 32px; text-align: center; }
  .submit-result h3 { margin: 16px 0; }
  .factors { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin-bottom: 20px; }
  .factor { padding: 4px 10px; border-radius: 20px; font-size: 12px; }
  .factor-positive { background: #052e1640; color: #4ade80; border: 1px solid #166534; }
  .factor-negative { background: #450a0a40; color: #f87171; border: 1px solid #991b1b; }
  .score-ring { display: flex; justify-content: center; }

  /* Buttons */
  .btn { padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-size: 14px; font-weight: 500; transition: all .15s; }
  .btn:disabled { opacity: .5; cursor: not-allowed; }
  .btn-primary { background: var(--accent); color: white; width: 100%; }
  .btn-primary:hover:not(:disabled) { background: #4f46e5; }
  .btn-ghost { background: var(--surface2); color: var(--text); border: 1px solid var(--border); }
  .btn-ghost:hover { background: var(--border); }

  /* Loading */
  .loading-full { display: flex; justify-content: center; padding: 80px; }
  .loading-spinner {
    width: 32px; height: 32px; border: 3px solid var(--border);
    border-top-color: var(--accent); border-radius: 50%; animation: spin .6s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .no-data { color: var(--muted); font-size: 13px; padding: 20px; text-align: center; }

  @media (max-width: 768px) {
    .charts-row { grid-template-columns: 1fr; }
    .main { padding: 12px; }
    .detail-panel { width: 100vw; }
  }
`;
