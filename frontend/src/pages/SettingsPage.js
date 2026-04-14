import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../App';
import {
  ArrowLeft, Plus, Trash, FloppyDisk, ToggleLeft, ToggleRight,
  GearSix, ShieldCheck, Gauge
} from '@phosphor-icons/react';

export default function SettingsPage() {
  const navigate = useNavigate();
  const [repos, setRepos] = useState([]);
  const [allRules, setAllRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);      // repo_full_name or "new"
  const [form, setForm] = useState(defaultForm());
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  function defaultForm() {
    return {
      repo_full_name: '', enabled: true, auto_post_comments: true,
      rate_limit_rpm: 30, severity_threshold: '',
      disabled_rules: [],
    };
  }

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [reposRes, rulesRes] = await Promise.all([
        api.get('/api/repo-settings'),
        api.get('/api/available-rules'),
      ]);
      setRepos(reposRes.data);
      setAllRules(rulesRes.data.rules || []);
    } catch (err) { console.error(err); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const startEdit = (repo) => {
    const rc = repo.rule_config || {};
    setForm({
      repo_full_name: repo.repo_full_name,
      enabled: repo.enabled ?? true,
      auto_post_comments: repo.auto_post_comments ?? true,
      rate_limit_rpm: repo.rate_limit_rpm ?? 30,
      severity_threshold: repo.severity_threshold || '',
      disabled_rules: rc.disabled_rules || [],
    });
    setEditing(repo.repo_full_name);
    setMsg('');
  };

  const startNew = () => {
    setForm(defaultForm());
    setEditing('new');
    setMsg('');
  };

  const toggleRule = (rule) => {
    setForm(f => ({
      ...f,
      disabled_rules: f.disabled_rules.includes(rule)
        ? f.disabled_rules.filter(r => r !== rule)
        : [...f.disabled_rules, rule],
    }));
  };

  const save = async () => {
    setSaving(true);
    setMsg('');
    try {
      const payload = {
        enabled: form.enabled,
        auto_post_comments: form.auto_post_comments,
        rate_limit_rpm: form.rate_limit_rpm,
        severity_threshold: form.severity_threshold || null,
        rule_config: form.disabled_rules.length > 0
          ? { disabled_rules: form.disabled_rules }
          : null,
      };

      if (editing === 'new') {
        await api.post('/api/repo-settings', { repo_full_name: form.repo_full_name, ...payload });
      } else {
        const [owner, name] = editing.split('/');
        await api.put(`/api/repo-settings/${owner}/${name}`, payload);
      }
      setMsg('Saved');
      setEditing(null);
      fetchData();
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Save failed');
    }
    setSaving(false);
  };

  const remove = async (repoFullName) => {
    const [owner, name] = repoFullName.split('/');
    try {
      await api.delete(`/api/repo-settings/${owner}/${name}`);
      fetchData();
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Delete failed');
    }
  };

  return (
    <div data-testid="settings-page" style={{ background: 'var(--bg-subtle)', minHeight: '100vh' }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '12px 24px',
        background: 'var(--bg-base)', borderBottom: '1px solid var(--border-default)',
        position: 'sticky', top: 0, zIndex: 50,
      }}>
        <button data-testid="back-to-dashboard" onClick={() => navigate('/')} style={{
          background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem',
        }}>
          <ArrowLeft size={16} /> Back
        </button>
        <div style={{ flex: 1 }} />
        <GearSix size={18} color="var(--text-tertiary)" />
        <span className="mono" style={{ fontSize: '0.75rem', fontWeight: 600 }}>Repository Settings</span>
      </div>

      <div style={{ maxWidth: 900, margin: '0 auto', padding: 24 }}>
        {/* Add new */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <span className="input-label">Configured Repositories ({repos.length})</span>
          <button data-testid="add-repo-button" className="btn-primary" onClick={startNew}
            style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem' }}>
            <Plus size={14} weight="bold" /> Add Repository
          </button>
        </div>

        {msg && <div className="mono fade-in" style={{ marginBottom: 16, fontSize: '0.75rem', color: msg === 'Saved' ? 'var(--success)' : 'var(--danger)' }}>{msg}</div>}

        {/* Editor */}
        {editing !== null && (
          <div data-testid="repo-settings-editor" className="fade-in" style={{
            background: 'var(--bg-base)', border: '1px solid var(--border-default)', padding: 24, marginBottom: 24,
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
              <div>
                <label className="input-label">Repository (owner/name)</label>
                <input data-testid="repo-name-input" className="input-field" placeholder="owner/repo-name"
                  value={form.repo_full_name} disabled={editing !== 'new'}
                  onChange={e => setForm(f => ({ ...f, repo_full_name: e.target.value }))} />
              </div>
              <div>
                <label className="input-label">Rate Limit (req/min)</label>
                <input data-testid="rate-limit-input" className="input-field" type="number" min={1} max={200}
                  value={form.rate_limit_rpm}
                  onChange={e => setForm(f => ({ ...f, rate_limit_rpm: parseInt(e.target.value) || 30 }))} />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 20 }}>
              <ToggleRow data-testid="toggle-enabled" label="Enabled" value={form.enabled}
                onChange={() => setForm(f => ({ ...f, enabled: !f.enabled }))} />
              <ToggleRow data-testid="toggle-auto-post" label="Auto-Post Comments" value={form.auto_post_comments}
                onChange={() => setForm(f => ({ ...f, auto_post_comments: !f.auto_post_comments }))} />
              <div>
                <label className="input-label">Min Severity</label>
                <select data-testid="severity-threshold-select" className="input-field" value={form.severity_threshold}
                  onChange={e => setForm(f => ({ ...f, severity_threshold: e.target.value }))}>
                  <option value="">All</option>
                  <option value="low">Low+</option>
                  <option value="medium">Medium+</option>
                  <option value="high">High only</option>
                </select>
              </div>
            </div>

            {/* Rule toggles */}
            <label className="input-label" style={{ marginBottom: 10, display: 'block' }}>
              Analysis Rules ({allRules.length - form.disabled_rules.length}/{allRules.length} enabled)
            </label>
            <div data-testid="rule-toggles-grid" style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 1,
              background: 'var(--border-default)', border: '1px solid var(--border-default)', marginBottom: 20,
            }}>
              {allRules.map(rule => {
                const enabled = !form.disabled_rules.includes(rule);
                return (
                  <button key={rule} data-testid={`rule-toggle-${rule}`}
                    onClick={() => toggleRule(rule)}
                    style={{
                      background: enabled ? 'var(--bg-base)' : 'var(--bg-muted)',
                      border: 'none', padding: '10px 14px', cursor: 'pointer', textAlign: 'left',
                      display: 'flex', alignItems: 'center', gap: 8,
                      transition: 'background-color 150ms ease-out',
                    }}>
                    <div style={{
                      width: 8, height: 8, borderRadius: 1,
                      background: enabled ? 'var(--success)' : 'var(--border-default)',
                      transition: 'background-color 150ms ease-out',
                    }} />
                    <span className="mono" style={{
                      fontSize: '0.7rem', color: enabled ? 'var(--text-primary)' : 'var(--text-tertiary)',
                    }}>{rule}</span>
                  </button>
                );
              })}
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button data-testid="save-settings-button" className="btn-primary" onClick={save} disabled={saving}
                style={{ padding: '8px 20px', display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem' }}>
                <FloppyDisk size={14} /> {saving ? 'Saving...' : 'Save'}
              </button>
              <button className="btn-ghost" onClick={() => setEditing(null)}
                style={{ padding: '8px 20px', fontSize: '0.8rem' }}>Cancel</button>
            </div>
          </div>
        )}

        {/* Repo list */}
        {loading ? (
          <div className="empty-state"><span className="mono loading-pulse">Loading...</span></div>
        ) : repos.length === 0 && editing === null ? (
          <div className="empty-state">
            <ShieldCheck size={40} weight="thin" style={{ opacity: 0.3, marginBottom: 12 }} />
            <p className="mono" style={{ fontSize: '0.8rem' }}>No repositories configured</p>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: 6 }}>
              Add a repository to customize analysis rules and settings.
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1, background: 'var(--border-default)', border: '1px solid var(--border-default)' }}>
            {repos.map(repo => (
              <div key={repo.repo_full_name} data-testid={`repo-row-${repo.repo_full_name}`}
                style={{
                  background: 'var(--bg-base)', padding: '14px 20px',
                  display: 'flex', alignItems: 'center', gap: 16,
                }}>
                <div style={{ flex: 1 }}>
                  <span className="mono" style={{ fontSize: '0.8rem', fontWeight: 500 }}>{repo.repo_full_name}</span>
                  <div style={{ display: 'flex', gap: 12, marginTop: 4 }}>
                    <span className={`badge ${repo.enabled ? 'badge-completed' : 'badge-failed'}`}>
                      {repo.enabled ? 'enabled' : 'disabled'}
                    </span>
                    <span className="badge badge-received">{repo.rate_limit_rpm} rpm</span>
                    {repo.auto_post_comments && <span className="badge badge-processed">auto-post</span>}
                    {repo.severity_threshold && <span className="badge badge-pending">min: {repo.severity_threshold}</span>}
                  </div>
                </div>
                <button data-testid={`edit-repo-${repo.repo_full_name}`} className="btn-ghost"
                  onClick={() => startEdit(repo)}
                  style={{ padding: '6px 14px', fontSize: '0.7rem' }}>Edit</button>
                <button data-testid={`delete-repo-${repo.repo_full_name}`}
                  onClick={() => remove(repo.repo_full_name)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--danger)', display: 'flex' }}>
                  <Trash size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ToggleRow({ label, value, onChange, ...rest }) {
  return (
    <div {...rest} onClick={onChange} style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label className="input-label">{label}</label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {value ? <ToggleRight size={24} weight="fill" color="var(--brand-primary)" /> : <ToggleLeft size={24} color="var(--text-tertiary)" />}
        <span className="mono" style={{ fontSize: '0.7rem', color: value ? 'var(--brand-primary)' : 'var(--text-tertiary)' }}>
          {value ? 'On' : 'Off'}
        </span>
      </div>
    </div>
  );
}
