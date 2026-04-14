import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, api } from '../App';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Line, ComposedChart } from 'recharts';
import {
  Broadcast, GitPullRequest, SignOut, ChartBar, GearSix, Users,
  ArrowClockwise, ArrowCounterClockwise, ChartLine
} from '@phosphor-icons/react';

const LOGO = "https://static.prod-images.emergentagent.com/jobs/08f97c6a-4df8-4239-81f2-dbdcc7b47b9e/images/09e2ef867473ccebed66e4b5c893cbb89459d2ede7a3e9e33cf3a79e672cb27a.png";

function StatusBadge({ status }) {
  return <span data-testid="webhook-status-badge" className={`badge badge-${status}`}>{status}</span>;
}

function ScoreDisplay({ score }) {
  const color = score >= 80 ? 'var(--success)' : score >= 50 ? 'var(--warning)' : 'var(--danger)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span className="mono" style={{ fontSize: '0.8rem', fontWeight: 600, color }}>{score}</span>
      <div className="score-bar">
        <div className="score-bar-fill" style={{ width: `${score}%`, background: color }} />
      </div>
    </div>
  );
}

function timeAgo(isoStr) {
  if (!isoStr) return '';
  const diff = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState('reviews');
  const [stats, setStats] = useState(null);
  const [webhookLogs, setWebhookLogs] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(true);
  const [replaying, setReplaying] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, logsRes, reviewsRes, trendsRes] = await Promise.all([
        api.get(`/api/stats`),
        api.get(`/api/webhook-logs`),
        api.get(`/api/reviews`),
        api.get(`/api/stats/trends?days=30`),
      ]);
      setStats(statsRes.data);
      setWebhookLogs(logsRes.data);
      setReviews(reviewsRes.data);
      setTrends(trendsRes.data);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const replayWebhook = async (logId) => {
    setReplaying(logId);
    try {
      await api.post(`/api/webhook-logs/${logId}/replay`, {});
      setTimeout(fetchData, 1500);
    } catch (err) {
      console.error('Replay failed:', err);
    }
    setReplaying(null);
  };

  return (
    <div className="dashboard-shell" data-testid="dashboard-container">
      {/* Header */}
      <header className="dash-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <img src={LOGO} alt="Logo" style={{ width: 28, height: 28 }} />
          <span className="mono" style={{ fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.05em' }}>
            PR Review Bot
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button data-testid="nav-settings" onClick={() => navigate('/settings')}
            className="btn-ghost" style={{ padding: '6px 12px', display: 'flex', alignItems: 'center', gap: 6 }}>
            <GearSix size={14} /> <span style={{ fontSize: '0.7rem' }}>Settings</span>
          </button>
          {user?.role === 'admin' && (
            <button data-testid="nav-team" onClick={() => navigate('/team')}
              className="btn-ghost" style={{ padding: '6px 12px', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Users size={14} /> <span style={{ fontSize: '0.7rem' }}>Team</span>
            </button>
          )}
          <span className="mono" data-testid="user-email-display" style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', letterSpacing: '0.05em', marginLeft: 8 }}>
            {user?.email}
          </span>
          <button data-testid="logout-button" onClick={logout}
            className="btn-ghost" style={{ padding: '6px 14px', display: 'flex', alignItems: 'center', gap: 6 }}>
            <SignOut size={16} /> <span style={{ fontSize: '0.75rem' }}>Logout</span>
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="dash-content">
        {/* Stats Grid */}
        <div className="stat-grid fade-in" style={{ marginBottom: 24 }}>
          <div className="stat-card">
            <span className="stat-label">Total Webhooks</span>
            <span className="stat-value" data-testid="stat-total-webhooks">{loading ? '—' : (stats?.total_webhooks ?? 0)}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Reviews</span>
            <span className="stat-value" data-testid="stat-total-reviews">{loading ? '—' : (stats?.total_reviews ?? 0)}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Completed</span>
            <span className="stat-value" data-testid="stat-completed-reviews" style={{ color: 'var(--success)' }}>{loading ? '—' : (stats?.completed_reviews ?? 0)}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Avg Score</span>
            <span className="stat-value" data-testid="stat-avg-score">{loading ? '—' : (stats?.avg_score ?? 0)}</span>
          </div>
        </div>

        {/* Tabs */}
        <div className="tab-row">
          <button data-testid="tab-reviews" className={`tab-btn ${tab === 'reviews' ? 'active' : ''}`} onClick={() => setTab('reviews')}>
            <GitPullRequest size={14} weight="bold" style={{ marginRight: 6, verticalAlign: -2 }} /> Reviews
          </button>
          <button data-testid="tab-webhooks" className={`tab-btn ${tab === 'webhooks' ? 'active' : ''}`} onClick={() => setTab('webhooks')}>
            <Broadcast size={14} weight="bold" style={{ marginRight: 6, verticalAlign: -2 }} /> Webhook Logs
          </button>
          <button data-testid="tab-trends" className={`tab-btn ${tab === 'trends' ? 'active' : ''}`} onClick={() => setTab('trends')}>
            <ChartLine size={14} weight="bold" style={{ marginRight: 6, verticalAlign: -2 }} /> Trends
          </button>
          <div style={{ flex: 1 }} />
          <button data-testid="refresh-data-button" onClick={fetchData} className="btn-ghost"
            style={{ padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 6, border: 'none' }}>
            <ArrowClockwise size={14} weight="bold" /> <span style={{ fontSize: '0.7rem' }}>Refresh</span>
          </button>
        </div>

        {/* Reviews Table */}
        {tab === 'reviews' && (
          <div className="fade-in">
            {reviews.length === 0 && !loading ? (
              <div className="empty-state">
                <ChartBar size={48} weight="thin" style={{ opacity: 0.3, marginBottom: 16 }} />
                <p className="mono" style={{ fontSize: '0.8rem', letterSpacing: '0.1em' }}>No reviews yet</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: 8 }}>Reviews will appear here when pull requests are processed.</p>
              </div>
            ) : (
              <table className="data-table" data-testid="pr-review-table">
                <thead><tr><th>PR</th><th>Repository</th><th>Author</th><th>Score</th><th>Status</th><th>Time</th></tr></thead>
                <tbody>
                  {reviews.map((r, i) => (
                    <tr key={r.id} data-testid={`review-row-${i}`} style={{ cursor: 'pointer' }} onClick={() => navigate(`/review/${r.id}`)}>
                      <td>
                        <span className="mono" style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-primary)' }}>#{r.pr_number}</span>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                          {r.pr_title?.slice(0, 50)}{r.pr_title?.length > 50 ? '...' : ''}
                        </div>
                      </td>
                      <td className="mono" style={{ fontSize: '0.75rem' }}>{r.repo_full_name}</td>
                      <td className="mono" style={{ fontSize: '0.75rem' }}>{r.pr_author}</td>
                      <td>{r.status === 'completed' ? <ScoreDisplay score={r.score} /> : '—'}</td>
                      <td><StatusBadge status={r.status} /></td>
                      <td className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{timeAgo(r.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Webhook Logs Table */}
        {tab === 'webhooks' && (
          <div className="fade-in">
            {webhookLogs.length === 0 && !loading ? (
              <div className="empty-state">
                <Broadcast size={48} weight="thin" style={{ opacity: 0.3, marginBottom: 16 }} />
                <p className="mono" style={{ fontSize: '0.8rem', letterSpacing: '0.1em' }}>No webhook events yet</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: 8 }}>Configure your GitHub App webhook to point to this server.</p>
              </div>
            ) : (
              <table className="data-table" data-testid="webhook-logs-table">
                <thead><tr><th>Event</th><th>Action</th><th>Repository</th><th>PR</th><th>Status</th><th>Time</th><th style={{ width: 60 }}></th></tr></thead>
                <tbody>
                  {webhookLogs.map((log, i) => (
                    <tr key={log.id} data-testid={`webhook-log-row-${i}`}>
                      <td className="mono" style={{ fontSize: '0.75rem', fontWeight: 500 }}>{log.event_type}</td>
                      <td className="mono" style={{ fontSize: '0.75rem' }}>{log.action}</td>
                      <td className="mono" style={{ fontSize: '0.75rem' }}>{log.repo_full_name}</td>
                      <td className="mono" style={{ fontSize: '0.75rem' }}>{log.pr_number ?? '—'}</td>
                      <td><StatusBadge status={log.status} /></td>
                      <td className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{timeAgo(log.created_at)}</td>
                      <td>
                        {log.event_type === 'pull_request' && log.pr_number && (
                          <button data-testid={`replay-btn-${i}`}
                            onClick={() => replayWebhook(log.id)}
                            disabled={replaying === log.id}
                            style={{
                              background: 'none', border: '1px solid var(--border-default)', cursor: 'pointer',
                              padding: '3px 8px', display: 'flex', alignItems: 'center', gap: 4,
                              color: 'var(--text-secondary)', fontSize: '0.65rem', fontFamily: "'JetBrains Mono', monospace",
                              transition: 'border-color 150ms',
                            }}>
                            <ArrowCounterClockwise size={12} />
                            {replaying === log.id ? '...' : 'Replay'}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Trends Chart */}
        {tab === 'trends' && (
          <div className="fade-in">
            {trends.length === 0 ? (
              <div className="empty-state">
                <ChartLine size={48} weight="thin" style={{ opacity: 0.3, marginBottom: 16 }} />
                <p className="mono" style={{ fontSize: '0.8rem', letterSpacing: '0.1em' }}>No trend data yet</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: 8 }}>Trends will appear after reviews are completed.</p>
              </div>
            ) : (
              <div data-testid="trends-chart-container">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, background: 'var(--border-default)', border: '1px solid var(--border-default)', marginBottom: 24 }}>
                  {/* Score Trend */}
                  <div style={{ background: 'var(--bg-base)', padding: 20 }}>
                    <span className="input-label" style={{ marginBottom: 12, display: 'block' }}>Average Score (30d)</span>
                    <ResponsiveContainer width="100%" height={220}>
                      <ComposedChart data={trends}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--bg-muted)" />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fontFamily: 'JetBrains Mono', fill: 'var(--text-tertiary)' }}
                          tickFormatter={d => d.slice(5)} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 10, fontFamily: 'JetBrains Mono', fill: 'var(--text-tertiary)' }} />
                        <Tooltip contentStyle={{ fontFamily: 'JetBrains Mono', fontSize: '0.7rem', border: '1px solid var(--border-default)', boxShadow: 'none' }} />
                        <Line type="monotone" dataKey="avg_score" stroke="var(--brand-primary)" strokeWidth={2} dot={{ r: 3 }} name="Avg Score" />
                        <Line type="monotone" dataKey="min_score" stroke="var(--danger)" strokeWidth={1} strokeDasharray="4 4" dot={false} name="Min" />
                        <Line type="monotone" dataKey="max_score" stroke="var(--success)" strokeWidth={1} strokeDasharray="4 4" dot={false} name="Max" />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                  {/* Review Count */}
                  <div style={{ background: 'var(--bg-base)', padding: 20 }}>
                    <span className="input-label" style={{ marginBottom: 12, display: 'block' }}>Reviews per Day (30d)</span>
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={trends}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--bg-muted)" />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fontFamily: 'JetBrains Mono', fill: 'var(--text-tertiary)' }}
                          tickFormatter={d => d.slice(5)} />
                        <YAxis tick={{ fontSize: 10, fontFamily: 'JetBrains Mono', fill: 'var(--text-tertiary)' }} />
                        <Tooltip contentStyle={{ fontFamily: 'JetBrains Mono', fontSize: '0.7rem', border: '1px solid var(--border-default)', boxShadow: 'none' }} />
                        <Bar dataKey="count" fill="var(--brand-primary)" radius={[2, 2, 0, 0]} name="Reviews" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                {/* Data table */}
                <table className="data-table" data-testid="trends-data-table">
                  <thead><tr><th>Date</th><th style={{ textAlign: 'right' }}>Reviews</th><th style={{ textAlign: 'right' }}>Avg</th><th style={{ textAlign: 'right' }}>Min</th><th style={{ textAlign: 'right' }}>Max</th></tr></thead>
                  <tbody>
                    {[...trends].reverse().map((t, i) => (
                      <tr key={t.date} data-testid={`trend-row-${i}`}>
                        <td className="mono" style={{ fontSize: '0.75rem' }}>{t.date}</td>
                        <td className="mono" style={{ fontSize: '0.75rem', textAlign: 'right' }}>{t.count}</td>
                        <td className="mono" style={{ fontSize: '0.75rem', textAlign: 'right', fontWeight: 600 }}>{t.avg_score}</td>
                        <td className="mono" style={{ fontSize: '0.75rem', textAlign: 'right', color: 'var(--danger)' }}>{t.min_score}</td>
                        <td className="mono" style={{ fontSize: '0.75rem', textAlign: 'right', color: 'var(--success)' }}>{t.max_score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
