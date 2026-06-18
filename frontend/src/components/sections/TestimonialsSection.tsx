import { t } from '../../styles/theme';

const TESTIMONIALS = [
  {
    text: 'Chuyến đi Phú Quốc cùng VinJourney thực sự tuyệt vời! Resort Vinpearl sang xịn, bãi biển đẹp không tả được. Sẽ quay lại vào năm sau!',
    name: 'Nguyễn Thị Lan',
    loc: 'Hà Nội · Tháng 5/2025',
  },
  {
    text: 'Đặt tour Hạ Long qua app cực kỳ dễ, giá hợp lý, thuyền rồng đẹp mê ly. Dịch vụ chăm sóc khách hàng rất chu đáo, gia đình mình rất hài lòng!',
    name: 'Trần Văn Minh',
    loc: 'TP.HCM · Tháng 3/2025',
  },
  {
    text: 'Hội An về đêm với đèn lồng lung linh, được tư vấn rất kỹ bởi VinJourney. Lần đầu tiên cảm giác được chăm sóc tốt đến vậy trong một chuyến du lịch!',
    name: 'Phạm Thu Hằng',
    loc: 'Đà Nẵng · Tháng 4/2025',
  },
];

export function TestimonialsSection() {
  return (
    <section style={{ padding: '100px 64px', background: t.bg }}>
      <h2 style={{ fontFamily: t.serif, fontSize: '40px', fontWeight: 600, color: t.ink, lineHeight: 1.15, margin: '0 0 48px', whiteSpace: 'nowrap' }}>
        Hành trình qua lời kể của <span style={{ fontStyle: 'italic' }}>du khách</span>
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '28px' }}>
        {TESTIMONIALS.map((item, i) => (
          <div
            key={i}
            style={{
              background: t.surface,
              border: `1px solid ${t.borderStrong}`,
              borderRadius: t.rPanel,
              padding: '32px 30px',
              display: 'flex', flexDirection: 'column',
              transition: 'box-shadow .25s, transform .25s, border-color .25s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.boxShadow = t.shadow; e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.borderColor = t.ink3; }}
            onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.transform = ''; e.currentTarget.style.borderColor = t.borderStrong; }}
          >
            <p style={{ fontFamily: t.serif, fontSize: '19px', fontStyle: 'italic', color: t.ink, lineHeight: 1.6, margin: '0 0 24px', flex: 1 }}>
              “{item.text}”
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Avatar name={item.name} />
              <div>
                <div style={{ fontFamily: t.font, fontSize: '14px', fontWeight: 600, color: t.ink }}>{item.name}</div>
                <div style={{ fontFamily: t.font, fontSize: '12px', color: t.ink3 }}>{item.loc}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Avatar({ name }: { name: string }) {
  const initial = name.trim().charAt(0);
  return (
    <div style={{
      width: '42px', height: '42px', borderRadius: '50%', flexShrink: 0,
      background: t.ink, color: '#FFFFFF',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: t.serif, fontSize: '18px', fontWeight: 600,
    }}>
      {initial}
    </div>
  );
}
