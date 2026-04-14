import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  ArrowLeft, GitPullRequest, CheckCircle,
  Warning, Info, XCircle, Clock
} from '@phosphor-icons/react';

const API = process.env.REACT_APP_BACKEND_URL;

function SeverityIcon({ severity }) {
  const map = {
    error: <XCircle size={16} weight="fill" color="var(--danger)" />,
    warning: <Warning size={16} weight="fill" color="var(--warning)" />,
    info: <Info size={16} weight="fill" color="var(--brand-primary)" />,
  };
  return map[severity] || map.info;
}

export default function ReviewDetailPage() {
  const { reviewId } = useParams();
  const navigate = useNavigate();
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${API}/api/reviews/${reviewId}`, { withCredentials: true });
        setReview(data);
      } catch (err) {
        setError('Review not found');
      } finally {
        setLoading(false);
      }
    })();
  }, [reviewId]);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <span className="mono loading-pulse" style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem', letterSpacing: '0.2em', textTransform: 'uppercase' }}>
          Loading review...
        </span>
      </div>
    );
  }

  if (error || !review) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 16 }}>
        <p className="mono" style={{ color: 'var(--danger)', fontSize: '0.8rem' }}>{error || 'Not found'}</p>
        <button className="btn-ghost" onClick={() => navigate('/')}>Back to Dashboard</button>
      </div>
    );
  }

  const scoreColor = review.score >= 80 ? 'var(--success)' : review.score >= 50 ? 'var(--warning)' : 'var(--danger)';
  const comments = review.comments || [];

  return (
    <div data-testid="review-detail-page" style={{ background: 'var(--bg-subtle)', minHeight: '100vh' }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '12px 24px',
        background: 'var(--bg-base)', borderBottom: '1px solid var(--border-default)',
        position: 'sticky', top: 0, zIndex: 50
      }}>
        <button
          data-testid="back-to-dashboard"
          onClick={() => navigate('/')}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)',
            fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem'
          }}
        >
          <ArrowLeft size={16} />
          Back
        </button>
      </div>

      <div style={{ maxWidth: 900, margin: '0 auto', padding: 24 }}>
        {/* Header Card */}
        <div className="review-detail-header fade-in">
          <GitPullRequest size={28} weight="bold" color="var(--brand-primary)" />
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span className="mono" style={{ fontSize: '0.8rem', fontWeight: 600 }}>
                {review.repo_full_name}#{review.pr_number}
              </span>
              <span className={`badge badge-${review.status}`}>{review.status}</span>
            </div>
            <h2 data-testid="review-pr-title" style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: 4 }}>
              {review.pr_title}
            </h2>
            <span className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
              by {review.pr_author}
            </span>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="mono" style={{ fontSize: '2.5rem', fontWeight: 700, color: scoreColor, lineHeight: 1 }}>
              {review.score}
            </div>
            <span className="mono" style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              / 100
            </span>
          </div>
        </div>

        {/* Summary */}
        <div style={{
          background: 'var(--bg-base)', border: '1px solid var(--border-default)',
          borderTop: 'none', padding: '20px 24px', marginBottom: 24
        }} className="fade-in fade-in-delay-1">
          <span className="input-label" style={{ marginBottom: 8 }}>Analysis Summary</span>
          <p data-testid="review-summary" style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
            {review.summary}
          </p>
        </div>

        {/* Comments */}
        <div style={{ marginBottom: 24 }}>
          <span className="input-label" style={{ marginBottom: 12, display: 'block' }}>
            Comments ({comments.length})
          </span>

          {comments.length === 0 ? (
            <div className="empty-state fade-in fade-in-delay-2" style={{ padding: 40 }}>
              <CheckCircle size={36} weight="thin" color="var(--success)" style={{ marginBottom: 12, opacity: 0.5 }} />
              <p className="mono" style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                No issues found. Clean code!
              </p>
            </div>
          ) : (
            comments.map((c, i) => (
              <div
                key={i}
                data-testid={`review-comment-${i}`}
                className={`review-comment-card severity-${c.severity} fade-in`}
                style={{ animationDelay: `${i * 50 + 100}ms` }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <SeverityIcon severity={c.severity} />
                  <span className="mono" style={{ fontSize: '0.75rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                    {c.path}:{c.line}
                  </span>
                  <span className={`badge badge-${c.severity === 'error' ? 'failed' : c.severity === 'warning' ? 'pending' : 'received'}`}>
                    {c.severity}
                  </span>
                </div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                  {c.body}
                </p>
              </div>
            ))
          )}
        </div>

        {/* PR Link */}
        {review.pr_url && (
          <div className="fade-in fade-in-delay-3" style={{ textAlign: 'center', paddingBottom: 40 }}>
            <a
              data-testid="view-on-github-link"
              href={review.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}
            >
              <GitPullRequest size={16} />
              View on GitHub
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
