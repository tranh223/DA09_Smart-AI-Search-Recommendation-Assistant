import { t } from '../../styles/theme';

export type Route = 'home' | 'hotels';

const LINKS: { label: string; route?: Route }[] = [
  { label: 'Điểm đến', route: 'home' },
  { label: 'Tour' },
  { label: 'Khách sạn', route: 'hotels' },
  { label: 'Vui chơi' },
  { label: 'Blog' },
];

export function NavBar({ active, onNavigate }: { active?: Route; onNavigate?: (route: Route) => void } = {}) {
  return (
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

      <a style={{
        background: t.navy,
        color: t.onNavy,
        padding: '11px 24px',
        borderRadius: t.rPill,
        fontFamily: t.font,
        fontSize: '14px',
        fontWeight: 600,
        cursor: 'pointer',
        textDecoration: 'none',
        display: 'inline-block',
        transition: 'background .15s, transform .15s',
      }}
        onMouseEnter={e => { e.currentTarget.style.background = t.navyHover; e.currentTarget.style.transform = 'translateY(-1px)'; }}
        onMouseLeave={e => { e.currentTarget.style.background = t.navy; e.currentTarget.style.transform = ''; }}
      >
        Đặt ngay
      </a>
    </nav>
  );
}
