import React, { useState } from 'react';
import { useAuth } from '../App';
import { GitPullRequest, Eye, EyeSlash } from '@phosphor-icons/react';

const LOGIN_BG = "https://static.prod-images.emergentagent.com/jobs/08f97c6a-4df8-4239-81f2-dbdcc7b47b9e/images/d5b138a931409a4a3df731a8de37586e06e20ae7314354900ff4947a58046e23.png";
const LOGO = "https://static.prod-images.emergentagent.com/jobs/08f97c6a-4df8-4239-81f2-dbdcc7b47b9e/images/09e2ef867473ccebed66e4b5c893cbb89459d2ede7a3e9e33cf3a79e672cb27a.png";

function formatApiError(detail) {
  if (detail == null) return "Something went wrong.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map(e => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default function LoginPage() {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPw, setShowPw] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (isRegister) {
        await register(email, password, name);
      } else {
        await login(email, password);
      }
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-split">
      {/* Form Panel */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 24px' }}>
        <div style={{ width: '100%', maxWidth: 380 }} className="fade-in">
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 48 }}>
            <img src={LOGO} alt="Logo" style={{ width: 36, height: 36 }} />
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem', fontWeight: 600, letterSpacing: '0.05em', color: 'var(--text-primary)' }}>
              PR Review Bot
            </span>
          </div>

          <h1 style={{ fontSize: '1.75rem', fontWeight: 600, marginBottom: 8, lineHeight: 1.2 }}>
            {isRegister ? 'Create account' : 'Sign in'}
          </h1>
          <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem', marginBottom: 32 }}>
            {isRegister ? 'Set up your monitoring dashboard access.' : 'Access your PR review dashboard.'}
          </p>

          {error && (
            <div data-testid="auth-error-message" style={{
              padding: '10px 14px', marginBottom: 20,
              border: '1px solid var(--danger)', color: 'var(--danger)',
              fontSize: '0.8rem', fontFamily: "'JetBrains Mono', monospace",
              background: 'rgba(255, 43, 43, 0.04)'
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {isRegister && (
              <div style={{ marginBottom: 16 }}>
                <label className="input-label" htmlFor="name">Name</label>
                <input
                  data-testid="register-name-input"
                  id="name"
                  type="text"
                  className="input-field"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Your name"
                  required={isRegister}
                />
              </div>
            )}

            <div style={{ marginBottom: 16 }}>
              <label className="input-label" htmlFor="email">Email</label>
              <input
                data-testid="login-email-input"
                id="email"
                type="email"
                className="input-field"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="admin@example.com"
                required
              />
            </div>

            <div style={{ marginBottom: 24 }}>
              <label className="input-label" htmlFor="password">Password</label>
              <div style={{ position: 'relative' }}>
                <input
                  data-testid="login-password-input"
                  id="password"
                  type={showPw ? 'text' : 'password'}
                  className="input-field"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Enter password"
                  required
                  style={{ paddingRight: 44 }}
                />
                <button
                  type="button"
                  data-testid="toggle-password-visibility"
                  onClick={() => setShowPw(!showPw)}
                  style={{
                    position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)',
                    display: 'flex', alignItems: 'center'
                  }}
                >
                  {showPw ? <EyeSlash size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <button
              data-testid="login-submit-button"
              type="submit"
              className="btn-primary"
              disabled={loading}
              style={{ width: '100%', marginBottom: 16 }}
            >
              {loading ? 'Processing...' : (isRegister ? 'Create Account' : 'Sign In')}
            </button>
          </form>

          <div style={{ textAlign: 'center' }}>
            <button
              data-testid="toggle-auth-mode"
              onClick={() => { setIsRegister(!isRegister); setError(''); }}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--brand-primary)', fontSize: '0.8rem',
                fontFamily: "'JetBrains Mono', monospace"
              }}
            >
              {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Register"}
            </button>
          </div>
        </div>
      </div>

      {/* Image Panel */}
      <div className="login-image-panel">
        <img src={LOGIN_BG} alt="Background" />
        <div className="login-image-overlay" />
        <div style={{
          position: 'absolute', bottom: 60, left: 48, right: 48, zIndex: 2, color: 'white'
        }}>
          <GitPullRequest size={32} weight="bold" style={{ marginBottom: 16, opacity: 0.8 }} />
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: 8, lineHeight: 1.3 }}>
            AI-Powered Code Reviews
          </h2>
          <p style={{ fontSize: '0.875rem', opacity: 0.7, lineHeight: 1.6 }}>
            Automated performance analysis for every pull request. Get instant feedback on code quality, security, and best practices.
          </p>
        </div>
      </div>
    </div>
  );
}
