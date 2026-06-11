const TESTIMONIALS = [
  {
    text: 'Chuyến đi Phú Quốc cùng VinJourney thực sự tuyệt vời! Resort Vinpearl sang xịn, bãi biển đẹp không tả được. Sẽ quay lại vào năm sau!',
    name: 'Nguyễn Thị Lan',
    loc: '📍 Hà Nội · Tháng 5/2025',
    avatarFill: '#F5DADA',
    avatarCircle: '#D42B2B',
    rotate: '0deg',
    marginTop: '0',
  },
  {
    text: 'Đặt tour Hạ Long qua app cực kỳ dễ, giá hợp lý, thuyền rồng đẹp mê ly. Dịch vụ chăm sóc khách hàng rất chu đáo, mình và gia đình rất hài lòng!',
    name: 'Trần Văn Minh',
    loc: '📍 TP.HCM · Tháng 3/2025',
    avatarFill: '#FDE8E0',
    avatarCircle: '#A01E1E',
    rotate: '-1deg',
    marginTop: '10px',
    borderColor: '#D42B2B',
  },
  {
    text: 'Hội An về đêm với đèn lồng lung linh, được tư vấn rất kỹ bởi VinJourney. Lần đầu tiên cảm giác được chăm sóc tốt đến vậy trong một chuyến du lịch!',
    name: 'Phạm Thu Hằng',
    loc: '📍 Đà Nẵng · Tháng 4/2025',
    avatarFill: '#FFF5EC',
    avatarCircle: '#D42B2B',
    rotate: '0.5deg',
    marginTop: '0',
  },
];

const WAVE_TOP = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 40' preserveAspectRatio='none'%3E%3Cpath d='M0 0 Q100 40 200 20 Q300 0 400 20 Q500 40 600 20 Q700 0 800 20 Q900 40 1000 20 Q1100 0 1200 20 L1200 40 L0 40Z' fill='%23FFFDF8'/%3E%3C/svg%3E")`;

export function TestimonialsSection() {
  return (
    <section style={{
      padding: '60px 40px 55px',
      background: '#FFF5EC',
      marginTop: '50px',
      position: 'relative',
    }}>
      <div style={{
        position: 'absolute',
        top: '-20px', left: 0, right: 0, height: '40px',
        backgroundImage: WAVE_TOP,
        backgroundSize: '100% 100%',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center',
      }} />
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: '28px' }}>
        <h2 style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '38px', fontWeight: 700, color: '#2A1A1A', lineHeight: 1.1, margin: 0 }}>
          Khách hàng <span style={{ color: '#D42B2B' }}>nói gì?</span> 💬
        </h2>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
        {TESTIMONIALS.map((t, i) => (
          <div key={i} style={{
            background: 'white',
            border: `2px solid ${t.borderColor ?? '#F5DADA'}`,
            borderRadius: '18px',
            padding: '20px',
            boxShadow: '3px 3px 0 #F5DADA',
            transform: `rotate(${t.rotate})`,
            marginTop: t.marginTop,
          }}>
            <div style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '52px', color: '#D42B2B', lineHeight: 0.8, marginBottom: '6px', opacity: 0.45 }}>"</div>
            <p style={{ fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '14px', color: '#5A3A3A', lineHeight: 1.7, marginBottom: '14px', fontStyle: 'italic' }}>
              {t.text}
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ width: '36px', height: '36px', borderRadius: '50%', border: '2px solid #F5DADA', overflow: 'hidden', flexShrink: 0 }}>
                <svg width="36" height="36" viewBox="0 0 36 36">
                  <circle cx="18" cy="18" r="18" fill={t.avatarFill}/>
                  <circle cx="18" cy="13" r="6.5" fill={t.avatarCircle} opacity="0.6"/>
                  <ellipse cx="18" cy="30" rx="11" ry="7" fill={t.avatarCircle} opacity="0.4"/>
                </svg>
              </div>
              <div>
                <div style={{ fontFamily: "'Pangolin', cursive", fontSize: '17px', color: '#2A1A1A' }}>{t.name}</div>
                <div style={{ fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '12px', color: '#5A3A3A' }}>{t.loc}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
