const WAVY_SVG = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='6'%3E%3Cpath d='M0 3 Q10 0 20 3 Q30 6 40 3 Q50 0 60 3 Q70 6 80 3 Q90 0 100 3 Q110 6 120 3 Q130 0 140 3 Q150 6 160 3 Q170 0 180 3 Q190 6 200 3' fill='none' stroke='%23D42B2B' stroke-width='1.5' opacity='0.35'/%3E%3C%2Fsvg%3E")`;

const LINKS = ['Điểm đến', 'Tour', 'Khách sạn', 'Vui chơi', 'Blog'];

export function NavBar() {
  return (
    <nav style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 40px',
      borderBottom: '2.5px solid #D42B2B',
      background: '#FFFDF8',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      <div style={{
        position: 'absolute',
        bottom: '-6px',
        left: 0,
        right: 0,
        height: '3px',
        backgroundImage: WAVY_SVG,
        backgroundRepeat: 'repeat-x',
        backgroundPosition: 'center',
      }} />

      <a href="#" style={{
        fontFamily: "'Baloo 2', sans-serif",
        fontSize: '26px',
        fontWeight: 700,
        color: '#D42B2B',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        textDecoration: 'none',
      }}>
        <svg width="34" height="34" viewBox="0 0 34 34" fill="none">
          <circle cx="17" cy="17" r="15" stroke="#D42B2B" strokeWidth="2.5" fill="#FDF3F3"/>
          <path d="M8 22 Q12 9 17 13 Q22 17 26 11" stroke="#D42B2B" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
          <circle cx="17" cy="13" r="2.5" fill="#D42B2B" opacity="0.7"/>
          <path d="M13 26 Q17 21 21 26" stroke="#D42B2B" strokeWidth="2" fill="none" strokeLinecap="round"/>
        </svg>
        VinJourney
      </a>

      <ul style={{ display: 'flex', gap: '26px', listStyle: 'none', margin: 0, padding: 0 }}>
        {LINKS.map(link => (
          <li key={link}>
            <a href="#"
              style={{ fontFamily: "'Pangolin', cursive", fontSize: '18px', color: '#2A1A1A', textDecoration: 'none', transition: 'color .2s' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#D42B2B')}
              onMouseLeave={e => (e.currentTarget.style.color = '#2A1A1A')}
            >
              {link}
            </a>
          </li>
        ))}
      </ul>

      <a href="#" style={{
        background: '#D42B2B',
        color: 'white',
        padding: '8px 22px',
        borderRadius: '99px',
        fontFamily: "'Pangolin', cursive",
        fontSize: '17px',
        border: '2.5px solid #A01E1E',
        cursor: 'pointer',
        boxShadow: '3px 3px 0 #A01E1E',
        textDecoration: 'none',
        display: 'inline-block',
        transition: 'transform .15s, box-shadow .15s',
      }}
        onMouseEnter={e => { e.currentTarget.style.transform = 'translate(-1px,-1px)'; e.currentTarget.style.boxShadow = '4px 4px 0 #A01E1E'; }}
        onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = '3px 3px 0 #A01E1E'; }}
      >
        ✈ Đặt ngay
      </a>
    </nav>
  );
}
