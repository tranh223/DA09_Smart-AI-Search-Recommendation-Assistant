import { ImageWithFallback } from '../common/ImageWithFallback';
import { t } from '../../styles/theme';

interface HeroSectionProps {
  onOpenChat: () => void;
}

const HERO_IMG = 'https://images.unsplash.com/photo-1528127269322-539801943592?w=1920&h=1280&fit=crop&auto=format&q=80';

export function HeroSection({ onOpenChat }: HeroSectionProps) {
  return (
    <section style={{ position: 'relative', minHeight: '620px', display: 'flex', alignItems: 'center', overflow: 'hidden' }}>
      {/* Ảnh nền full-bleed */}
      <div style={{ position: 'absolute', inset: 0, background: t.bgSoft }}>
        <ImageWithFallback
          src={HERO_IMG}
          alt="Vịnh Hạ Long, Việt Nam"
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(90deg, rgba(20,19,17,0.72) 0%, rgba(20,19,17,0.45) 42%, rgba(20,19,17,0.10) 75%)',
        }} />
      </div>

      {/* Nội dung */}
      <div style={{ position: 'relative', zIndex: 2, padding: '0 64px', maxWidth: '720px' }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: '9px',
          color: 'rgba(255,255,255,0.85)', fontFamily: t.font, fontSize: '12px',
          fontWeight: 600, letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: '24px',
        }}>
          <span style={{ width: '24px', height: '1px', background: 'rgba(255,255,255,0.6)' }} />
          Khám phá Việt Nam cùng Vingroup
        </div>
        <h1 style={{
          fontFamily: t.serif, fontSize: '64px', fontWeight: 600,
          lineHeight: 1.08, color: '#FFFFFF', margin: '0 0 22px', letterSpacing: '-0.01em',
        }}>
          Mỗi chuyến đi là một<br /><span style={{ fontStyle: 'italic', fontWeight: 500 }}>kỷ niệm</span> đáng nhớ
        </h1>
        <p style={{
          fontSize: '17px', color: 'rgba(255,255,255,0.82)', lineHeight: 1.7,
          maxWidth: '480px', marginBottom: '36px', fontFamily: t.font,
        }}>
          Trải nghiệm những điểm đến tuyệt vời nhất Việt Nam — từ biển xanh Phú Quốc đến phố cổ Hội An — với dịch vụ 5 sao của Vingroup.
        </p>
        <div style={{ display: 'flex', gap: '14px', alignItems: 'center', flexWrap: 'wrap' }}>
          <a style={{
            background: '#FFFFFF', color: t.ink,
            fontFamily: t.font, fontSize: '15px', fontWeight: 600,
            padding: '15px 34px', borderRadius: t.rPill, cursor: 'pointer',
            textDecoration: 'none', display: 'inline-block',
            transition: 'transform .15s, box-shadow .15s', boxShadow: t.shadow,
          }}
            onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; }}
            onMouseLeave={e => { e.currentTarget.style.transform = ''; }}
          >
            Khám phá ngay
          </a>
          <a
            onClick={onOpenChat}
            style={{
              fontFamily: t.font, fontSize: '15px', fontWeight: 600,
              color: '#FFFFFF', padding: '15px 30px', borderRadius: t.rPill,
              border: '1px solid rgba(255,255,255,0.5)', background: 'transparent',
              cursor: 'pointer', textDecoration: 'none', display: 'inline-block',
              transition: 'background .15s, border-color .15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; e.currentTarget.style.borderColor = '#FFFFFF'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.5)'; }}
          >
            Hỏi trợ lý AI
          </a>
        </div>
      </div>
    </section>
  );
}
