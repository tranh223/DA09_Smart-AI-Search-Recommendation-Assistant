// AdminPage — placeholder trang quản trị.

import { t } from '../styles/theme';
import { NavBar, type Route } from '../components/layout/NavBar';
import { useAuth } from '../hooks/useAuth';

export function AdminPage({ onNavigate }: { onNavigate?: (route: Route) => void }) {
  const { user, role } = useAuth();

  return (
    <div style={{
      fontFamily: t.font,
      background: t.bg,
      color: t.ink,
      minHeight: '100vh',
    }}>
      <NavBar active="home" onNavigate={onNavigate} />

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - 80px)',
        padding: '40px 24px',
      }}>
        {/* Admin badge */}
        <div style={{
          width: 80,
          height: 80,
          borderRadius: 20,
          background: `linear-gradient(135deg, ${t.accent}, ${t.accentDark})`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 36,
          marginBottom: 24,
          boxShadow: '0 12px 40px rgba(14,110,99,0.25)',
        }}>
          👑
        </div>

        <h1 style={{
          fontFamily: t.serif,
          fontSize: 32,
          fontWeight: 700,
          color: t.ink,
          margin: '0 0 12px',
        }}>
          Trang Quản trị
        </h1>

        <p style={{
          fontSize: 16,
          color: t.ink2,
          textAlign: 'center',
          maxWidth: 480,
          lineHeight: 1.7,
          margin: '0 0 32px',
        }}>
          Xin chào <strong>{user?.name}</strong>! Bạn đang đăng nhập với vai trò{' '}
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            background: t.accentSoft,
            color: t.accentDark,
            padding: '2px 10px',
            borderRadius: t.rPill,
            fontSize: 13,
            fontWeight: 600,
          }}>
            👑 Admin
          </span>
        </p>

        {/* Placeholder cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 20,
          width: '100%',
          maxWidth: 720,
        }}>
          {[
            { icon: '📊', title: 'Thống kê', desc: 'Dashboard & analytics', href: '/dashboard' },
            { icon: '👥', title: 'Người dùng', desc: 'Quản lý tài khoản' },
            { icon: '🏨', title: 'Khách sạn', desc: 'Quản lý dữ liệu' },
          ].map(card => (
            <div key={card.title} onClick={() => {
                if (card.href) {
                  window.history.pushState({}, '', card.href);
                  window.dispatchEvent(new PopStateEvent('popstate'));
                }
              }} style={{
              background: t.surface,
              border: `1px solid ${t.border}`,
              borderRadius: 16,
              padding: '28px 24px',
              textAlign: 'center',
              transition: 'box-shadow .2s, transform .2s',
              cursor: card.href ? 'pointer' : 'default',
            }}
              onMouseEnter={e => {
                e.currentTarget.style.boxShadow = t.shadow;
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.boxShadow = 'none';
                e.currentTarget.style.transform = '';
              }}
            >
              <div style={{ fontSize: 32, marginBottom: 12 }}>{card.icon}</div>
              <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>{card.title}</div>
              <div style={{ fontSize: 13, color: t.ink3 }}>{card.desc}</div>
              <div style={{
                marginTop: 16,
                padding: '6px 16px',
                borderRadius: t.rPill,
                border: `1px dashed ${t.border}`,
                fontSize: 12,
                color: t.ink3,
                display: 'inline-block',
              }}>
                {card.href ? 'Mở' : 'Đang phát triển...'}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
