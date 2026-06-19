import { t } from '../../styles/theme';

type IconKind = 'plane' | 'resort' | 'park' | 'shield';

const FEATURES: { icon: IconKind; title: string; desc: string }[] = [
  { icon: 'plane', title: 'Bay thẳng', desc: 'Vé máy bay ưu đãi từ VinAir đến 200+ điểm đến' },
  { icon: 'resort', title: 'Nghỉ dưỡng 5 sao', desc: 'Hệ thống Vinpearl Resort đẳng cấp toàn quốc' },
  { icon: 'park', title: 'Vui chơi cực đã', desc: 'VinWonders — công viên giải trí lớn nhất Việt Nam' },
  { icon: 'shield', title: 'An tâm tuyệt đối', desc: 'Bảo hiểm du lịch & hỗ trợ 24/7 mọi lúc mọi nơi' },
];

export function FeaturesStrip() {
  return (
    <div style={{
      margin: '90px 64px 0',
      paddingTop: '48px',
      borderTop: `1px solid ${t.border}`,
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: '48px',
    }}>
      {FEATURES.map((f, i) => (
        <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <FeatureIcon kind={f.icon} />
          <div style={{ fontFamily: t.serif, fontSize: '21px', fontWeight: 600, color: t.ink }}>{f.title}</div>
          <div style={{ fontFamily: t.font, fontSize: '14px', color: t.ink2, lineHeight: 1.65 }}>{f.desc}</div>
        </div>
      ))}
    </div>
  );
}

function FeatureIcon({ kind }: { kind: IconKind }) {
  const p = { stroke: t.accent, strokeWidth: 1.4, fill: 'none', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  const common = { width: 30, height: 30, viewBox: '0 0 24 24' };
  switch (kind) {
    case 'plane':
      return <svg {...common}><path {...p} d="M2 14l20-8-8 20-3-7-9-5z" /></svg>;
    case 'resort':
      return <svg {...common}><path {...p} d="M4 21V8l8-4 8 4v13" /><path {...p} d="M9 21v-6h6v6" /></svg>;
    case 'park':
      return <svg {...common}><circle {...p} cx="12" cy="12" r="8" /><circle {...p} cx="12" cy="12" r="2.5" /><path {...p} d="M12 4v3M12 17v3M4 12h3M17 12h3" /></svg>;
    case 'shield':
      return <svg {...common}><path {...p} d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" /><path {...p} d="M9 12l2 2 4-4" /></svg>;
  }
}
