import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, api } from '../App';
import { ArrowLeft, Users, UserPlus, Trash, ShieldCheck, Crown } from '@phosphor-icons/react';

export default function TeamPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [team, setTeam] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showInvite, setShowInvite] = useState(false);
  const [inviteForm, setInviteForm] = useState({ email: '', password: '', name: '' });
  const [inviting, setInviting] = useState(false);

  const isAdmin = user?.role === 'admin';

  const fetchTeam = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/api/team`);
      setTeam(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load team');
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchTeam(); }, [fetchTeam]);

  const updateRole = async (email, newRole) => {
    try {
      await api.put(`/api/team/${email}/role`, { role: newRole });
      fetchTeam();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update role');
    }
  };

  const removeMember = async (email) => {
    try {
      await api.delete(`/api/team/${email}`);
      fetchTeam();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove user');
    }
  };

  const inviteUser = async (e) => {
    e.preventDefault();
    setInviting(true);
    setError('');
    try {
      await api.post(`/api/auth/register`, {
        email: inviteForm.email,
        password: inviteForm.password,
        name: inviteForm.name || 'Team Member',
      });
      setShowInvite(false);
      setInviteForm({ email: '', password: '', name: '' });
      fetchTeam();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create user');
    }
    setInviting(false);
  };

  const roleIcon = (role) => {
    if (role === 'admin') return <Crown size={14} weight="fill" color="var(--warning)" />;
    if (role === 'member') return <ShieldCheck size={14} color="var(--brand-primary)" />;
    return <Users size={14} color="var(--text-tertiary)" />;
  };

  return (
    <div data-testid="team-page" style={{ background: 'var(--bg-subtle)', minHeight: '100vh' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '12px 24px',
        background: 'var(--bg-base)', borderBottom: '1px solid var(--border-default)',
        position: 'sticky', top: 0, zIndex: 50,
      }}>
        <button data-testid="back-to-dashboard-team" onClick={() => navigate('/')} style={{
          background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem',
        }}>
          <ArrowLeft size={16} /> Back
        </button>
        <div style={{ flex: 1 }} />
        <Users size={18} color="var(--text-tertiary)" />
        <span className="mono" style={{ fontSize: '0.75rem', fontWeight: 600 }}>Team Management</span>
      </div>

      <div style={{ maxWidth: 700, margin: '0 auto', padding: 24 }}>
        {error && (
          <div className="mono fade-in" style={{ marginBottom: 16, padding: '10px 14px', fontSize: '0.75rem', color: 'var(--danger)', border: '1px solid var(--danger)', background: 'rgba(255,43,43,0.04)' }}>
            {typeof error === 'string' ? error : JSON.stringify(error)}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <span className="input-label">Team Members ({team.length})</span>
          {isAdmin && (
            <button data-testid="add-member-button" className="btn-primary"
              onClick={() => setShowInvite(!showInvite)}
              style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem' }}>
              <UserPlus size={14} weight="bold" /> Add Member
            </button>
          )}
        </div>

        {/* Invite form */}
        {showInvite && (
          <form data-testid="invite-form" onSubmit={inviteUser} className="fade-in" style={{
            background: 'var(--bg-base)', border: '1px solid var(--border-default)', padding: 20, marginBottom: 20,
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 14 }}>
              <div>
                <label className="input-label">Name</label>
                <input data-testid="invite-name" className="input-field" placeholder="Name"
                  value={inviteForm.name} onChange={e => setInviteForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div>
                <label className="input-label">Email</label>
                <input data-testid="invite-email" className="input-field" type="email" placeholder="email@example.com" required
                  value={inviteForm.email} onChange={e => setInviteForm(f => ({ ...f, email: e.target.value }))} />
              </div>
              <div>
                <label className="input-label">Password</label>
                <input data-testid="invite-password" className="input-field" type="password" placeholder="Temp password" required
                  value={inviteForm.password} onChange={e => setInviteForm(f => ({ ...f, password: e.target.value }))} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button data-testid="invite-submit" type="submit" className="btn-primary" disabled={inviting}
                style={{ padding: '8px 20px', fontSize: '0.8rem' }}>
                {inviting ? 'Creating...' : 'Create User'}
              </button>
              <button type="button" className="btn-ghost" onClick={() => setShowInvite(false)}
                style={{ padding: '8px 20px', fontSize: '0.8rem' }}>Cancel</button>
            </div>
          </form>
        )}

        {/* Team list */}
        {loading ? (
          <div className="empty-state"><span className="mono loading-pulse">Loading...</span></div>
        ) : (
          <table className="data-table" data-testid="team-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Joined</th>
                {isAdmin && <th style={{ width: 80 }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {team.map((m, i) => (
                <tr key={m.email} data-testid={`team-row-${i}`}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{
                        width: 30, height: 30, borderRadius: 2, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        background: 'var(--bg-muted)', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.7rem', fontWeight: 600,
                        color: 'var(--text-secondary)',
                      }}>
                        {(m.name || m.email).charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 500 }}>{m.name || '—'}</div>
                        <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{m.email}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    {isAdmin && m.email !== user.email ? (
                      <select data-testid={`role-select-${i}`} className="input-field"
                        value={m.role || 'user'}
                        onChange={e => updateRole(m.email, e.target.value)}
                        style={{ padding: '4px 8px', fontSize: '0.75rem', width: 'auto' }}>
                        <option value="admin">Admin</option>
                        <option value="member">Member</option>
                        <option value="viewer">Viewer</option>
                      </select>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        {roleIcon(m.role)}
                        <span className="mono" style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                          {m.role || 'user'}
                          {m.email === user.email && ' (you)'}
                        </span>
                      </div>
                    )}
                  </td>
                  <td className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
                    {m.created_at ? new Date(m.created_at).toLocaleDateString() : '—'}
                  </td>
                  {isAdmin && (
                    <td>
                      {m.email !== user.email && (
                        <button data-testid={`remove-member-${i}`}
                          onClick={() => removeMember(m.email)}
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--danger)', display: 'flex' }}>
                          <Trash size={16} />
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
