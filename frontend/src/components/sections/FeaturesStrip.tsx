const FEATURES = [
  { icon: '✈️', title: 'Bay thẳng', desc: 'Vé máy bay ưu đãi từ VinAir đến 200+ điểm đến' },
  { icon: '🏨', title: 'Nghỉ dưỡng 5★', desc: 'Hệ thống Vinpearl Resort đẳng cấp toàn quốc' },
  { icon: '🎡', title: 'Vui chơi cực đã', desc: 'VinWonders — công viên giải trí lớn nhất Việt Nam' },
  { icon: '🔒', title: 'An tâm tuyệt đối', desc: 'Bảo hiểm du lịch & hỗ trợ 24/7 mọi lúc mọi nơi' },
];

export function FeaturesStrip() {
  return (
    <div style={{
      margin: '50px 40px 0',
      background: '#D42B2B',
      borderRadius: '20px',
      padding: '26px 36px',
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: '20px',
      border: '2px solid #A01E1E',
      boxShadow: '5px 5px 0 #A01E1E',
      position: 'relative',
      overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40'%3E%3Ccircle cx='20' cy='20' r='1.2' fill='white' opacity='0.08'/%3E%3C/svg%3E")`,
        backgroundRepeat: 'repeat',
        pointerEvents: 'none',
      }} />
      {FEATURES.map((f, i) => (
        <div key={i} style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '8px',
          position: 'relative', zIndex: 1,
          paddingLeft: i > 0 ? '20px' : undefined,
          borderLeft: i > 0 ? '1px solid rgba(255,255,255,0.2)' : undefined,
        }}>
          <div style={{ fontSize: '30px', lineHeight: 1 }}>{f.icon}</div>
          <div style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '19px', fontWeight: 700, color: 'white' }}>{f.title}</div>
          <div style={{ fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '13px', color: 'rgba(255,255,255,0.82)', lineHeight: 1.5 }}>{f.desc}</div>
        </div>
      ))}
    </div>
  );
}
