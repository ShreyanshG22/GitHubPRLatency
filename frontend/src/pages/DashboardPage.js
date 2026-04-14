import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import axios from 'axios';
import {
  Broadcast, GitPullRequest, SignOut, ChartBar,
  ArrowClockwise, CheckCircle, XCircle, Clock, Lightning
} from '@phosphor-icons/react';

const API = process.env.REACT_APP_BACKEND_URL;
const LOGO = "https://static.prod-images.emergentagent.com/jobs/08f97c6a-4df8-4239-81f2-dbdcc7b47b9e/images/09e2ef867473ccebed66e4b5c893cbb89459d2ede7a3e9e33cf3a79e672cb27a.png";

function StatusBadge({ status }) {
  const cls = `badge badge-${status}`;
  return <span data-testid="webhook-status-badge" className={cls}>{status}</span>;
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
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, logsRes, reviewsRes] = await Promise.all([
        axios.get(`${API}/api/stats`, { withCredentials: true }),
        axios.get(`${API}/api/webhook-logs`, { withCredentials: true }),
        axios.get(`${API}/api/reviews`, { withCredentials: true }),
      ]);
      setStats(statsRes.data);
      setWebhookLogs(logsRes.data);
      setReviews(reviewsRes.data);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

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
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span className="mono" data-testid="user-email-display" style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>
            {user?.email}
          </span>
          <button
            data-testid="logout-button"
            onClick={logout}
            className="btn-ghost"
            style={{ padding: '6px 14px', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <SignOut size={16} />
            <span style={{ fontSize: '0.75rem' }}>Logout</span>
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="dash-content">
        {/* Stats Grid */}
        <div className="stat-grid fade-in" style={{ marginBottom: 24 }}>
          <div className="stat-card">
            <span className="stat-label">Total Webhooks</span>
            <span className="stat-value" data-testid="stat-total-webhooks">
              {loading ? '—' : (stats?.total_webhooks ?? 0)}
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Reviews</span>
            <span className="stat-value" data-testid="stat-total-reviews">
              {loading ? '—' : (stats?.total_reviews ?? 0)}
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Completed</span>
            <span className="stat-value" data-testid="stat-completed-reviews" style={{ color: 'var(--success)' }}>
              {loading ? '—' : (stats?.completed_reviews ?? 0)}
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Avg Score</span>
            <span className="stat-value" data-testid="stat-avg-score">
              {loading ? '—' : (stats?.avg_score ?? 0)}
            </span>
          </div>
        </div>

        {/* Tabs */}
        <div className="tab-row">
          <button
            data-testid="tab-reviews"
            className={`tab-btn ${tab === 'reviews' ? 'active' : ''}`}
            onClick={() => setTab('reviews')}
          >
            <GitPullRequest size={14} weight="bold" style={{ marginRight: 6, verticalAlign: -2 }} />
            Reviews
          </button>
          <button
            data-testid="tab-webhooks"
            className={`tab-btn ${tab === 'webhooks' ? 'active' : ''}`}
            onClick={() => setTab('webhooks')}
          >
            <Broadcast size={14} weight="bold" style={{ marginRight: 6, verticalAlign: -2 }} />
            Webhook Logs
          </button>
          <div style={{ flex: 1 }} />
          <button
            data-testid="refresh-data-button"
            onClick={fetchData}
            className="btn-ghost"
            style={{ padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 6, border: 'none' }}
          >
            <ArrowClockwise size={14} weight="bold" />
            <span style={{ fontSize: '0.7rem' }}>Refresh</span>
          </button>
        </div>

        {/* Reviews Table */}
        {tab === 'reviews' && (
          <div className="fade-in">
            {reviews.length === 0 && !loading ? (
              <div className="empty-state">
                <ChartBar size={48} weight="thin" style={{ opacity: 0.3, marginBottom: 16 }} />
                <p className="mono" style={{ fontSize: '0.8rem', letterSpacing: '0.1em' }}>
                  No reviews yet
                </p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: 8 }}>
                  Reviews will appear here when pull requests are processed.
                </p>
              </div>
            ) : (
              <table className="data-table" data-testid="pr-review-table">
                <thead>
                  <tr>
                    <th>PR</th>
                    <th>Repository</th>
                    <th>Author</th>
                    <th>Score</th>
                    <th>Status</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {reviews.map((r, i) => (
                    <tr
                      key={r.id}
                      data-testid={`review-row-${i}`}
                      style={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/review/${r.id}`)}
                    >
                      <td>
                        <span className="mono" style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                          #{r.pr_number}
                        </span>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                          {r.pr_title?.slice(0, 50)}{r.pr_title?.length > 50 ? '...' : ''}
                        </div>
                      </td>
                      <td className="mono" style={{ fontSize: '0.75rem' }}>{r.repo_full_name}</td>
                      <td className="mono" style={{ fontSize: '0.75rem' }}>{r.pr_author}</td>
                      <td>{r.status === 'completed' ? <ScoreDisplay score={r.score} /> : '—'}</td>
                      <td><StatusBadge status={r.status} /></td>
                      <td className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
                        {timeAgo(r.created_at)}
                      </td>
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
                <p className="mono" style={{ fontSize: '0.8rem', letterSpacing: '0.1em' }}>
                  No webhook events yet
                </p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: 8 }}>
                  Configure your GitHub App webhook to point to this server.
                </p>
              </div>
            ) : (
              <table className="data-table" data-testid="webhook-logs-table">
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Action</th>
                    <th>Repository</th>
                    <th>PR</th>
                    <th>Status</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {webhookLogs.map((log, i) => (
                    <tr key={log.id} data-testid={`webhook-log-row-${i}`}>
                      <td className="mono" style={{ fontSize: '0.75rem', fontWeight: 500 }}>{log.event_type}</td>
                      <td className="mono" style={{ fontSize: '0.75rem' }}>{log.action}</td>
                      <td className="mono" style={{ fontSize: '0.75rem' }}>{log.repo_full_name}</td>
                      <td className="mono" style={{ fontSize: '0.75rem' }}>{log.pr_number ?? '—'}</td>
                      <td><StatusBadge status={log.status} /></td>
                      <td className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
                        {timeAgo(log.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
