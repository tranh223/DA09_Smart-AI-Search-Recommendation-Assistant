import { ImageWithFallback } from '../common/ImageWithFallback';
import { formatPrice, primaryImage, type Hotel } from '../../services/hotels';
import { t } from '../../styles/theme';

export function HotelCard({ hotel, onClick }: { hotel: Hotel; onClick: () => void }) {
  const img = primaryImage(hotel);
  const location = [hotel.area, hotel.city].filter(Boolean).join(', ');

  return (
    <div
      onClick={onClick}
      style={{
        cursor: 'pointer', minWidth: 0,
        background: t.surface,
        border: `1px solid ${t.borderStrong}`,
        borderRadius: t.rCard,
        padding: '12px 12px 16px',
        transition: 'box-shadow .25s, transform .25s, border-color .25s',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.boxShadow = t.shadow;
        e.currentTarget.style.transform = 'translateY(-4px)';
        e.currentTarget.style.borderColor = t.ink3;
        const im = e.currentTarget.querySelector('img');
        if (im) (im as HTMLImageElement).style.transform = 'scale(1.05)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.boxShadow = 'none';
        e.currentTarget.style.transform = '';
        e.currentTarget.style.borderColor = t.borderStrong;
        const im = e.currentTarget.querySelector('img');
        if (im) (im as HTMLImageElement).style.transform = '';
      }}
    >
      <div style={{
        width: '100%', aspectRatio: '4 / 3', overflow: 'hidden', position: 'relative',
        background: t.bgSoft, borderRadius: '9px', marginBottom: '14px',
      }}>
        {img ? (
          <ImageWithFallback
            src={img}
            alt={hotel.name}
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', transition: 'transform .5s ease' }}
          />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: t.ink3, fontSize: '13px' }}>
            Không có ảnh
          </div>
        )}
        {hotel.is_luxury && (
          <div style={{
            position: 'absolute', top: '12px', left: '12px',
            background: 'rgba(255,255,255,0.92)', color: t.ink,
            fontFamily: t.font, fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em',
            padding: '5px 11px', borderRadius: t.rPill,
          }}>
            LUXURY
          </div>
        )}
      </div>

      <div style={{
        fontFamily: t.serif, fontSize: '19px', fontWeight: 600, color: t.ink,
        marginBottom: '5px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {hotel.name}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px', fontSize: '13px', color: t.ink2, minWidth: 0 }}>
        {hotel.review_score != null && <RatingPill score={hotel.review_score} count={hotel.review_count} />}
        {location && (
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>
            {hotel.review_score != null ? '· ' : ''}{location}
          </span>
        )}
      </div>
      <div style={{ fontFamily: t.font, fontSize: '16px', fontWeight: 600, color: t.ink }}>
        {formatPrice(hotel.min_price)}
        {hotel.min_price ? <span style={{ fontSize: '13px', fontWeight: 400, color: t.ink3 }}> /đêm</span> : null}
      </div>
    </div>
  );
}

export function RatingPill({ score, count }: { score: number; count?: number }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', whiteSpace: 'nowrap' }}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill={t.accent}>
        <path d="M12 2l2.9 6.3 6.8.6-5.1 4.5 1.5 6.7L12 17.8 5.9 20.6l1.5-6.7L2.3 8.9l6.8-.6z" />
      </svg>
      <span style={{ fontSize: '13px', fontWeight: 600, color: t.ink }}>{score}</span>
      {count ? <span style={{ fontSize: '13px', color: t.ink3 }}>({count})</span> : null}
    </span>
  );
}

export function HotelSkeletonCard() {
  return (
    <div style={{
      background: t.surface, border: `1px solid ${t.borderStrong}`, borderRadius: t.rCard, padding: '12px 12px 16px',
    }}>
      <div style={{ width: '100%', aspectRatio: '4 / 3', background: t.bgSoft, borderRadius: '9px', marginBottom: '14px' }} />
      <div style={{ height: '18px', width: '70%', background: t.bgSoft, borderRadius: '6px', marginBottom: '10px' }} />
      <div style={{ height: '13px', width: '45%', background: t.bgSoft, borderRadius: '6px' }} />
    </div>
  );
}
