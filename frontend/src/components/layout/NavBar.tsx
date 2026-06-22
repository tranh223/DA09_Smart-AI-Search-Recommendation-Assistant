import { useState, useRef, useEffect } from 'react';
import { t } from '../../styles/theme';
import { useAuth } from '../../hooks/useAuth';

export type Route = 'home' | 'hotels';

const LINKS: { label: string; route?: Route }[] = [
  { label: 'Điểm đến', route: 'home' },
  { label: 'Tour' },
  { label: 'Khách sạn', route: 'hotels' },
  { label: 'Vui chơi' },
  { label: 'Blog' },
];

export function NavBar({ active, onNavigate }: { active?: Route; onNavigate?: (route: Route) => void } = {}) {
  const { user, role, logout } = useAuth();
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    if (!showDropdown) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showDropdown]);

  // Extract initials for avatar
  const initials = user?.name
    ? user.name
        .split(' ')
        .map(w => w[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : '?';

  return (
    <>
      <nav style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '20px 64px',
        borderBottom: `1px solid ${t.border}`,
        background: 'rgba(250,248,244,0.82)',
        backdropFilter: 'blur(12px)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <a onClick={() => onNavigate?.('home')} style={{
          fontFamily: t.serif,
          fontSize: '25px',
          fontWeight: 600,
          letterSpacing: '0.01em',
          color: t.ink,
          textDecoration: 'none',
          cursor: 'pointer',
        }}>
          VinJourney
        </a>

        <ul style={{ display: 'flex', gap: '36px', listStyle: 'none', margin: 0, padding: 0 }}>
          {LINKS.map(link => {
            const isActive = !!link.route && link.route === active;
            return (
              <li key={link.label}>
                <a
                  onClick={() => link.route && onNavigate?.(link.route)}
                  style={{
                    fontFamily: t.font, fontSize: '14px', fontWeight: 500,
                    color: isActive ? t.ink : t.ink2,
                    textDecoration: 'none', transition: 'color .2s', cursor: 'pointer',
                    paddingBottom: '3px',
                    borderBottom: isActive ? `1px solid ${t.ink}` : '1px solid transparent',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.color = t.ink)}
                  onMouseLeave={e => (e.currentTarget.style.color = isActive ? t.ink : t.ink2)}
                >
                  {link.label}
                </a>
              </li>
            );
          })}
        </ul>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* ── Logged in: Avatar + dropdown ── */}
          <div ref={dropdownRef} style={{ position: 'relative' }}>
            <button
              onClick={() => setShowDropdown(d => !d)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                background: 'none',
                border: `1px solid ${t.border}`,
                borderRadius: t.rPill,
                padding: '6px 16px 6px 6px',
                cursor: 'pointer',
                transition: 'border-color .2s, box-shadow .2s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = t.borderStrong;
                e.currentTarget.style.boxShadow = '0 2px 8px rgba(28,27,25,0.08)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = t.border;
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              {/* Avatar circle */}
              <div style={{
                width: 32,
                height: 32,
                borderRadius: '50%',
                background: `linear-gradient(135deg, ${t.accent}, ${t.accentDark})`,
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: t.font,
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: '0.02em',
                flexShrink: 0,
              }}>
                {initials}
              </div>
              <span style={{
                fontFamily: t.font,
                fontSize: 13,
                fontWeight: 500,
                color: t.ink,
                maxWidth: 120,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {user?.name || 'User'}
              </span>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{
                transition: 'transform .2s',
                transform: showDropdown ? 'rotate(180deg)' : '',
              }}>
                <path d="M3 4.5L6 7.5L9 4.5" stroke={t.ink3} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>

            {/* Dropdown */}
            {showDropdown && (
              <div style={{
                position: 'absolute',
                top: 'calc(100% + 8px)',
                right: 0,
                minWidth: 200,
                background: t.surface,
                border: `1px solid ${t.border}`,
                borderRadius: 12,
                boxShadow: t.shadow,
                padding: '8px 0',
                animation: 'navDropIn .15s ease',
                zIndex: 200,
              }}>
                {/* User info */}
                <div style={{
                  padding: '12px 16px',
                  borderBottom: `1px solid ${t.border}`,
                }}>
                  <div style={{ fontFamily: t.font, fontSize: 14, fontWeight: 600, color: t.ink }}>
                    {user?.name}
                  </div>
                  <div style={{ fontFamily: t.font, fontSize: 12, color: t.ink3, marginTop: 2 }}>
                    {role === 'admin' ? '👑 Admin' : '👤 User'} · {user?.user_id}
                  </div>
                </div>

                {/* Logout */}
                <button
                  onClick={() => { logout(); setShowDropdown(false); }}
                  style={{
                    width: '100%',
                    padding: '10px 16px',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    fontFamily: t.font,
                    fontSize: 13,
                    fontWeight: 500,
                    color: '#B91C1C',
                    textAlign: 'left',
                    transition: 'background .15s',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#FEF2F2')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'none')}
                >
                  <span>🚪</span> Đăng xuất
                </button>
              </div>
            )}
          </div>
        </div>
      </nav>

      {/* Dropdown animation */}
      <style>{`
        @keyframes navDropIn {
          from { opacity: 0; transform: translateY(-6px) }
          to { opacity: 1; transform: translateY(0) }
        }
      `}</style>
    </>
  );
}
