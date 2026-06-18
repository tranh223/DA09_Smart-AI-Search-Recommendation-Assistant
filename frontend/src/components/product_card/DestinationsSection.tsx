import { useState } from 'react';
import { HotelCard, HotelSkeletonCard } from './HotelCard';
import { HotelDetailModal } from './HotelDetailModal';
import { useHotels } from '../../hooks/useHotels';
import { type Hotel } from '../../services/hotels';
import { t } from '../../styles/theme';

export function DestinationsSection({ onSeeAll }: { onSeeAll?: () => void }) {
  const { hotels, loading, error } = useHotels({ limit: 8, sort_by: 'review_score:desc' });
  const [selected, setSelected] = useState<Hotel | null>(null);

  return (
    <section style={{ padding: '90px 64px 30px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: '40px' }}>
        <div>
          <div style={{ fontFamily: t.font, fontSize: '12px', fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', color: t.accent, marginBottom: '12px' }}>
            Được yêu thích
          </div>
          <h2 style={{ fontFamily: t.serif, fontSize: '40px', fontWeight: 600, color: t.ink, lineHeight: 1.1, margin: 0 }}>
            Khách sạn nổi bật
          </h2>
        </div>
        <a
          onClick={onSeeAll}
          style={{ fontFamily: t.font, fontSize: '14px', fontWeight: 600, color: t.ink, cursor: 'pointer', textDecoration: 'none', borderBottom: `1px solid ${t.ink}`, paddingBottom: '3px' }}
        >
          Xem tất cả
        </a>
      </div>

      {error && (
        <div style={{
          border: `1px solid ${t.border}`, background: '#FDF3F3', color: '#9C3B3B',
          borderRadius: t.rCard, padding: '16px 18px', fontSize: '14px', marginBottom: '20px',
        }}>
          Không tải được danh sách khách sạn: {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '32px' }}>
        {loading
          ? Array.from({ length: 4 }).map((_, i) => <HotelSkeletonCard key={i} />)
          : hotels.slice(0, 4).map((h) => (
              <HotelCard key={h.id} hotel={h} onClick={() => setSelected(h)} />
            ))}
      </div>

      {!loading && !error && hotels.length === 0 && (
        <div style={{ color: t.ink2, fontSize: '15px' }}>Chưa có khách sạn nào.</div>
      )}

      <HotelDetailModal hotelId={selected?.id ?? null} fallback={selected} onClose={() => setSelected(null)} />
    </section>
  );
}
