import { t } from '../../styles/theme';

const DEST_LINKS = ['Phú Quốc', 'Hạ Long', 'Hội An', 'Đà Nẵng', 'Nha Trang'];
const SERVICE_LINKS = ['Đặt tour', 'Vé máy bay', 'Khách sạn', 'Cho thuê xe', 'Bảo hiểm'];
const SUPPORT_LINKS = ['Về chúng tôi', 'Liên hệ', 'FAQ', 'Chính sách', 'Blog du lịch'];

export function Footer() {
  return (
    <>
      <footer style={{
        background: t.navy,
        color: '#FFFFFF',
        padding: '64px 64px 56px',
        display: 'grid',
        gridTemplateColumns: '2fr 1fr 1fr 1fr',
        gap: '48px',
      }}>
        <div>
          <span style={{ fontFamily: t.serif, fontSize: '26px', fontWeight: 600, color: '#FFFFFF', marginBottom: '16px', display: 'block' }}>
            VinJourney
          </span>
          <p style={{ fontFamily: t.font, fontSize: '13px', color: 'rgba(255,255,255,0.6)', lineHeight: 1.7, maxWidth: '250px' }}>
            Khám phá Việt Nam trọn vẹn hơn với hệ sinh thái du lịch Vingroup — từ máy bay, khách sạn đến vui chơi giải trí.
          </p>
        </div>
        <FooterCol title="Điểm đến" links={DEST_LINKS} />
        <FooterCol title="Dịch vụ" links={SERVICE_LINKS} />
        <FooterCol title="Hỗ trợ" links={SUPPORT_LINKS} />
      </footer>
      <div style={{
        background: t.navy,
        textAlign: 'center',
        padding: '22px',
        fontFamily: t.font,
        fontSize: '12px',
        letterSpacing: '0.04em',
        color: 'rgba(255,255,255,0.4)',
        borderTop: '1px solid rgba(255,255,255,0.1)',
      }}>
        © 2025 VinJourney — thuộc hệ sinh thái Vingroup
      </div>
    </>
  );
}

function FooterCol({ title, links }: { title: string; links: string[] }) {
  return (
    <div>
      <h4 style={{ fontFamily: t.font, fontSize: '15px', fontWeight: 600, marginBottom: '14px', color: '#FFFFFF', margin: '0 0 14px' }}>{title}</h4>
      {links.map(link => (
        <a key={link} href="#" style={{
          display: 'block',
          fontFamily: t.font,
          fontSize: '13px',
          color: 'rgba(255,255,255,0.6)',
          textDecoration: 'none',
          marginBottom: '9px',
          transition: 'color .2s',
        }}
          onMouseEnter={e => (e.currentTarget.style.color = t.accent)}
          onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.6)')}
        >
          {link}
        </a>
      ))}
    </div>
  );
}
