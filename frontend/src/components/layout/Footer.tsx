const DEST_LINKS = ['Phú Quốc', 'Hạ Long', 'Hội An', 'Đà Nẵng', 'Nha Trang'];
const SERVICE_LINKS = ['Đặt tour', 'Vé máy bay', 'Khách sạn', 'Cho thuê xe', 'Bảo hiểm'];
const SUPPORT_LINKS = ['Về chúng tôi', 'Liên hệ', 'FAQ', 'Chính sách', 'Blog du lịch'];

export function Footer() {
  return (
    <>
      <footer style={{
        background: '#2A1A1A',
        color: 'white',
        padding: '36px 40px',
        display: 'grid',
        gridTemplateColumns: '2fr 1fr 1fr 1fr',
        gap: '36px',
      }}>
        <div>
          <span style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '24px', fontWeight: 700, color: '#F5DADA', marginBottom: '10px', display: 'block' }}>
            ✦ VinJourney
          </span>
          <p style={{ fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '13px', color: 'rgba(255,255,255,0.6)', lineHeight: 1.7, maxWidth: '230px' }}>
            Khám phá Việt Nam trọn vẹn hơn với hệ sinh thái du lịch Vingroup — từ máy bay, khách sạn đến vui chơi giải trí.
          </p>
        </div>
        <FooterCol title="Điểm đến" links={DEST_LINKS} />
        <FooterCol title="Dịch vụ" links={SERVICE_LINKS} />
        <FooterCol title="Hỗ trợ" links={SUPPORT_LINKS} />
      </footer>
      <div style={{
        background: 'rgba(0,0,0,0.3)',
        textAlign: 'center',
        padding: '13px',
        fontFamily: "'Pangolin', cursive",
        fontSize: '15px',
        color: 'rgba(255,255,255,0.4)',
        borderTop: '1px dashed rgba(212,43,43,0.3)',
      }}>
        ✦ © 2025 VinJourney — thuộc hệ sinh thái Vingroup · Thiết kế với ❤ cho những chuyến đi đáng nhớ ✦
      </div>
    </>
  );
}

function FooterCol({ title, links }: { title: string; links: string[] }) {
  return (
    <div>
      <h4 style={{ fontFamily: "'Pangolin', cursive", fontSize: '19px', marginBottom: '12px', color: '#F5DADA', margin: '0 0 12px' }}>{title}</h4>
      {links.map(link => (
        <a key={link} href="#" style={{
          display: 'block',
          fontFamily: "'Be Vietnam Pro', sans-serif",
          fontSize: '13px',
          color: 'rgba(255,255,255,0.6)',
          textDecoration: 'none',
          marginBottom: '7px',
          transition: 'color .2s',
        }}
          onMouseEnter={e => (e.currentTarget.style.color = '#F5DADA')}
          onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.6)')}
        >
          {link}
        </a>
      ))}
    </div>
  );
}
