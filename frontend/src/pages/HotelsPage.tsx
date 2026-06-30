import { useState, useEffect } from 'react';
import { NavBar, type Route } from '../components/layout/NavBar';
import { Footer } from '../components/layout/Footer';
import { CHAT_DOCK_WIDTH } from '../components/chat/ChatBot';
import { HotelCard, HotelSkeletonCard } from '../components/product_card/HotelCard';
import { HotelDetailModal } from '../components/product_card/HotelDetailModal';
import { useHotels } from '../hooks/useHotels';
import { getHotel, type Hotel, type HotelListParams, type RecoQuery } from '../services/hotels';
import { t } from '../styles/theme';

const PAGE_SIZE = 12;

const SORT_OPTIONS: { label: string; value: string }[] = [
  { label: 'Đánh giá cao nhất', value: 'review_score:desc' },
  { label: 'Hạng sao cao nhất', value: 'star_rating:desc' },
  { label: 'Giá thấp → cao', value: 'price:asc' },
  { label: 'Giá cao → thấp', value: 'price:desc' },
];

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '11px 14px',
  borderRadius: t.rBtn,
  border: `1px solid ${t.border}`,
  background: t.bg,
  fontFamily: t.font,
  fontSize: '14px',
  color: t.ink,
  outline: 'none',
};

type Mode = 'reco' | 'all';

function normalizeText(value?: string): string {
  return (value ?? '').trim().toLowerCase();
}

function filterRecommendedHotels(hotels: Hotel[], filters: HotelListParams): Hotel[] {
  const city = normalizeText(filters.city);
  const minStars = filters.star_rating_min;

  let result = hotels.filter((hotel) => {
    if (city && !normalizeText(`${hotel.city ?? ''} ${hotel.area ?? ''} ${hotel.address ?? ''}`).includes(city)) {
      return false;
    }
    if (minStars != null && (hotel.star_rating ?? 0) < minStars) {
      return false;
    }
    return true;
  });

  switch (filters.sort_by) {
    case 'price:asc':
      result = [...result].sort((a, b) => (a.min_price ?? Number.MAX_SAFE_INTEGER) - (b.min_price ?? Number.MAX_SAFE_INTEGER));
      break;
    case 'price:desc':
      result = [...result].sort((a, b) => (b.min_price ?? 0) - (a.min_price ?? 0));
      break;
    case 'star_rating:desc':
      result = [...result].sort((a, b) => (b.star_rating ?? 0) - (a.star_rating ?? 0));
      break;
    case 'review_score:desc':
    default:
      result = [...result].sort((a, b) => (b.review_score ?? 0) - (a.review_score ?? 0));
      break;
  }

  return result;
}

export function HotelsPage({
  onNavigate,
  chatOpen = false,
  recoQuery = null,
  initialFilters = null,
}: {
  onNavigate?: (route: Route) => void;
  chatOpen?: boolean;
  recoQuery?: RecoQuery | null;
  initialFilters?: HotelListParams | null;
}) {
  const [selected, setSelected] = useState<Hotel | null>(null);
  const [mode, setMode] = useState<Mode>('all');
  const [hydratedRecoHotels, setHydratedRecoHotels] = useState<Hotel[] | null>(null);
  const [hydratingReco, setHydratingReco] = useState(false);

  // Bộ lọc người dùng tự đặt (áp dụng chồng lên gợi ý)
  const [filters, setFilters] = useState<HotelListParams>({ sort_by: 'review_score:desc' });
  const [page, setPage] = useState(1);

  // Giá trị nhập tạm (chỉ áp dụng khi bấm "Tìm")
  const [cityDraft, setCityDraft] = useState('');
  const [starDraft, setStarDraft] = useState('');
  const recoHotelIds = recoQuery?.hotels?.map((hotel) => hotel.id).join(',') ?? '';

  // Có gợi ý mới → chuyển sang chế độ gợi ý; mất gợi ý → quay về tất cả.
  useEffect(() => {
    setMode(recoQuery ? 'reco' : 'all');
    setPage(1);
  }, [recoQuery]);

  useEffect(() => {
    if (!recoQuery?.hotels?.length) {
      setHydratedRecoHotels(null);
      setHydratingReco(false);
      return;
    }

    let alive = true;
    setHydratingReco(true);
    setHydratedRecoHotels(recoQuery.hotels);

    Promise.all(
      recoQuery.hotels.map((hotel) =>
        getHotel(hotel.id)
          .then((detail) => ({
            ...hotel,
            ...detail,
            min_price: hotel.min_price ?? detail.min_price,
          }))
          .catch(() => hotel),
      ),
    )
      .then((hotels) => {
        if (alive) setHydratedRecoHotels(hotels);
      })
      .finally(() => {
        if (alive) setHydratingReco(false);
      });

    return () => {
      alive = false;
    };
  }, [recoHotelIds]);

  useEffect(() => {
    if (!initialFilters) return;
    setMode('all');
    setPage(1);
    setFilters((current) => ({
      ...current,
      ...initialFilters,
      city: initialFilters.city || undefined,
      star_rating_min: initialFilters.star_rating_min,
      sort_by: initialFilters.sort_by ?? current.sort_by,
    }));
    setCityDraft(initialFilters.city ?? '');
    setStarDraft(initialFilters.star_rating_min != null ? String(initialFilters.star_rating_min) : '');
  }, [initialFilters]);

  // Bộ lọc người dùng đặt (chỉ lấy khoá có giá trị để không ghi đè gợi ý)
  const userFilters: HotelListParams = {
    sort_by: filters.sort_by,
    ...(filters.city ? { city: filters.city } : {}),
    ...(filters.star_rating_min != null ? { star_rating_min: filters.star_rating_min } : {}),
  };
  const base = mode === 'reco' && recoQuery ? recoQuery.params : {};
  const query: HotelListParams = { ...base, ...userFilters, page, limit: PAGE_SIZE };

  const directRecoHotels = mode === 'reco' && recoQuery?.hotels?.length ? (hydratedRecoHotels ?? recoQuery.hotels) : null;
  const directFilteredHotels = directRecoHotels ? filterRecommendedHotels(directRecoHotels, userFilters) : null;
  const directPageHotels = directFilteredHotels?.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) ?? null;
  const hotelState = useHotels(query, !directRecoHotels);
  const hotels = directPageHotels ?? hotelState.hotels;
  const total = directFilteredHotels?.length ?? hotelState.total;
  const loading = directRecoHotels ? hydratingReco : hotelState.loading;
  const error = directRecoHotels ? null : hotelState.error;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function applyFilters() {
    setPage(1);
    setFilters((f) => ({
      ...f,
      city: cityDraft.trim() || undefined,
      star_rating_min: starDraft ? Number(starDraft) : undefined,
    }));
  }

  function changeSort(value: string) {
    setPage(1);
    setFilters((f) => ({ ...f, sort_by: value }));
  }

  function switchMode(m: Mode) {
    setMode(m);
    setPage(1);
  }

  return (
    <div style={{
      fontFamily: t.font,
      background: t.bg,
      color: t.ink,
      overflowX: 'hidden',
      minHeight: '100vh',
      paddingRight: chatOpen ? CHAT_DOCK_WIDTH : 0,
      transition: 'padding-right .3s ease',
    }}>
      <NavBar active="hotels" onNavigate={onNavigate} />

      {/* Header */}
      <section style={{ padding: '64px 64px 16px' }}>
        <h1 style={{ fontFamily: t.serif, fontSize: '46px', fontWeight: 600, margin: '0 0 10px', lineHeight: 1.08 }}>
          Khách sạn cho chuyến đi
        </h1>
        <p style={{ fontFamily: t.font, fontSize: '15px', color: t.ink2, margin: 0 }}>
          {loading
            ? 'Đang tải…'
            : mode === 'reco' && recoQuery
              ? `${total.toLocaleString('vi-VN')} khách sạn gợi ý · ${recoQuery.label}`
              : `${total.toLocaleString('vi-VN')} khách sạn trên khắp Việt Nam`}
        </p>
      </section>

      {/* Toggle Gợi ý ⇄ Tất cả (chỉ khi có gợi ý từ VinBot) */}
      {recoQuery && (
        <div style={{ padding: '8px 64px 0' }}>
          <div style={{
            display: 'inline-flex', gap: '4px', padding: '4px',
            background: t.bgSoft, borderRadius: t.rPill, border: `1px solid ${t.border}`,
          }}>
            <SegBtn active={mode === 'reco'} onClick={() => switchMode('reco')}>Gợi ý từ VinBot</SegBtn>
            <SegBtn active={mode === 'all'} onClick={() => switchMode('all')}>Tất cả khách sạn</SegBtn>
          </div>
        </div>
      )}

      {/* Bộ lọc — áp dụng cho cả hai chế độ */}
      <div style={{
        background: t.surface,
        border: `1px solid ${t.border}`,
        borderRadius: t.rPanel,
        padding: '22px 26px',
        margin: '16px 64px 0',
        boxShadow: t.shadowSoft,
        display: 'grid',
        gridTemplateColumns: '2fr 1fr 1.4fr auto',
        gap: '18px',
        alignItems: 'end',
      }}>
        <Field label="Thành phố">
          <input
            style={inputStyle}
            placeholder="Hồ Chí Minh, Đà Nẵng, Hạ Long..."
            value={cityDraft}
            onChange={(e) => setCityDraft(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && applyFilters()}
          />
        </Field>
        <Field label="Hạng sao tối thiểu">
          <select style={inputStyle} value={starDraft} onChange={(e) => setStarDraft(e.target.value)}>
            <option value="">Tất cả</option>
            <option value="3">3 sao trở lên</option>
            <option value="4">4 sao trở lên</option>
            <option value="5">5 sao</option>
          </select>
        </Field>
        <Field label="Sắp xếp">
          <select style={inputStyle} value={filters.sort_by} onChange={(e) => changeSort(e.target.value)}>
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </Field>
        <button
          onClick={applyFilters}
          style={{
            background: t.navy, color: t.onNavy, padding: '12px 28px', borderRadius: t.rBtn,
            fontFamily: t.font, fontSize: '15px', fontWeight: 600, border: 'none',
            cursor: 'pointer', whiteSpace: 'nowrap', transition: 'background .15s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = t.navyHover)}
          onMouseLeave={(e) => (e.currentTarget.style.background = t.navy)}
        >
          Tìm
        </button>
      </div>

      {/* Lưới khách sạn */}
      <section style={{ padding: '40px 64px 64px' }}>
        {error && (
          <div style={{
            border: `1px solid ${t.border}`, background: '#FDF3F3', color: '#9C3B3B',
            borderRadius: t.rCard, padding: '16px 18px', fontSize: '14px', marginBottom: '20px',
          }}>
            Không tải được danh sách khách sạn: {error}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${chatOpen ? 3 : 4}, 1fr)`, gap: '32px' }}>
          {loading
            ? Array.from({ length: PAGE_SIZE }).map((_, i) => <HotelSkeletonCard key={i} />)
            : hotels.map((h) => <HotelCard key={h.id} hotel={h} onClick={() => setSelected(h)} />)}
        </div>

        {!loading && !error && hotels.length === 0 && (
          <div style={{ color: t.ink2, fontSize: '15px', padding: '20px 0' }}>
            Không tìm thấy khách sạn phù hợp. Thử bỏ bớt bộ lọc nhé.
          </div>
        )}

        {/* Phân trang */}
        {!loading && totalPages > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '14px', marginTop: '40px' }}>
            <PageBtn disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>← Trước</PageBtn>
            <span style={{ fontFamily: t.font, fontSize: '14px', fontWeight: 500, color: t.ink2 }}>
              Trang {page} / {totalPages}
            </span>
            <PageBtn disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>Sau →</PageBtn>
          </div>
        )}
      </section>

      <Footer />
      <HotelDetailModal hotelId={selected?.id ?? null} fallback={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function SegBtn({ children, active, onClick }: { children: React.ReactNode; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        fontFamily: t.font, fontSize: '14px', fontWeight: 600,
        padding: '8px 18px', borderRadius: t.rPill, border: 'none', cursor: 'pointer',
        background: active ? t.surface : 'transparent',
        color: active ? t.ink : t.ink2,
        boxShadow: active ? t.shadowSoft : 'none',
        transition: 'background .15s, color .15s',
      }}
    >
      {children}
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label style={{ display: 'block', fontFamily: t.font, fontSize: '11px', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: t.ink3, marginBottom: '8px' }}>
        {label}
      </label>
      {children}
    </div>
  );
}

function PageBtn({ children, disabled, onClick }: { children: React.ReactNode; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: t.surface,
        color: disabled ? t.ink3 : t.ink,
        padding: '9px 18px',
        borderRadius: t.rBtn,
        fontFamily: t.font,
        fontSize: '14px',
        fontWeight: 600,
        border: `1px solid ${t.border}`,
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.6 : 1,
      }}
    >
      {children}
    </button>
  );
}
