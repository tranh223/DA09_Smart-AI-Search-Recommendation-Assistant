import { useEffect, useState } from 'react';
import { ImageWithFallback } from '../common/ImageWithFallback';
import { RatingPill } from './HotelCard';
import {
  getHotel,
  getHotelImages,
  formatPrice,
  type Hotel,
  type HotelImage,
} from '../../services/hotels';
import { t } from '../../styles/theme';

interface Props {
  hotelId: number | null;
  fallback?: Hotel | null; // data đã có từ list, hiện ngay trong lúc tải chi tiết
  onClose: () => void;
}

export function HotelDetailModal({ hotelId, fallback, onClose }: Props) {
  const [hotel, setHotel] = useState<Hotel | null>(null);
  const [images, setImages] = useState<HotelImage[]>([]);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (hotelId == null) return;
    let alive = true;
    setHotel(fallback ?? null);
    setImages(fallback?.images ?? []);
    setActive(0);
    setLoading(true);
    setError(null);

    Promise.all([getHotel(hotelId), getHotelImages(hotelId).catch(() => [])])
      .then(([detail, imgs]) => {
        if (!alive) return;
        setHotel(detail);
        const merged = imgs.length ? imgs : detail.images;
        setImages(merged.length ? merged : (fallback?.images ?? []));
      })
      .catch((err) => alive && setError(err?.message ?? 'Không tải được chi tiết'))
      .finally(() => alive && setLoading(false));

    return () => {
      alive = false;
    };
  }, [hotelId, fallback]);

  // Đóng bằng phím Esc + khoá scroll nền
  useEffect(() => {
    if (hotelId == null) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [hotelId, onClose]);

  if (hotelId == null) return null;

  const cover = images[active]?.url;
  const location = [hotel?.area, hotel?.city, hotel?.country].filter(Boolean).join(', ');

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(21,32,51,.5)',
        backdropFilter: 'blur(4px)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: t.surface,
          borderRadius: t.rPanel,
          border: `1px solid ${t.ink}`,
          boxShadow: t.shadowLg,
          width: 'min(1060px, 100%)',
          maxHeight: '88vh',
          display: 'flex',
          overflow: 'hidden',
          position: 'relative',
          fontFamily: t.font,
          color: t.ink,
        }}
      >
        {/* Nút đóng */}
        <button
          onClick={onClose}
          aria-label="Đóng"
          style={{
            position: 'absolute',
            top: '14px',
            right: '14px',
            zIndex: 5,
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            border: 'none',
            background: 'rgba(255,255,255,0.92)',
            color: t.ink,
            fontSize: '18px',
            cursor: 'pointer',
            lineHeight: 1,
            boxShadow: t.shadowSoft,
          }}
        >
          ✕
        </button>

        {/* ── Cột trái: ảnh + thông tin chung + tiện ích ── */}
        <div className="no-scrollbar" style={{ flex: '1 1 56%', minWidth: 0, overflowY: 'auto' }}>
          {/* Ảnh lớn */}
          <div style={{ width: '100%', height: '300px', background: t.bgSoft, overflow: 'hidden', position: 'relative' }}>
            {cover ? (
              <ImageWithFallback
                src={cover}
                alt={hotel?.name ?? 'Khách sạn'}
                style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
              />
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: t.ink3 }}>
                {loading ? 'Đang tải ảnh…' : 'Không có ảnh'}
              </div>
            )}
            {hotel?.is_luxury && (
              <div style={{
                position: 'absolute', top: '16px', left: '16px',
                background: 'rgba(22,34,61,0.9)', color: '#FFFFFF',
                fontFamily: t.font, fontSize: '11px', fontWeight: 600, letterSpacing: '0.04em',
                padding: '5px 12px', borderRadius: t.rPill,
              }}>
                LUXURY
              </div>
            )}
          </div>

          {/* Thumbnail */}
          {images.length > 1 && (
            <div className="no-scrollbar" style={{ display: 'flex', gap: '8px', padding: '14px 24px 0', overflowX: 'auto' }}>
              {images.slice(0, 8).map((img, i) => (
                <button
                  key={i}
                  onClick={() => setActive(i)}
                  style={{
                    flex: '0 0 auto',
                    width: '74px',
                    height: '54px',
                    borderRadius: '10px',
                    overflow: 'hidden',
                    border: i === active ? `2px solid ${t.accent}` : `1px solid ${t.border}`,
                    padding: 0,
                    cursor: 'pointer',
                    background: t.bgSoft,
                  }}
                >
                  <ImageWithFallback
                    src={img.url}
                    alt={`Ảnh ${i + 1}`}
                    style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                  />
                </button>
              ))}
            </div>
          )}

          {/* Thông tin chung */}
          <div style={{ padding: '20px 24px 28px' }}>
            <h2 style={{ fontFamily: t.serif, fontSize: '25px', fontWeight: 600, margin: '0 0 10px', lineHeight: 1.2, paddingRight: '40px' }}>
              {hotel?.name ?? 'Đang tải…'}
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              {hotel?.review_score != null && <RatingPill score={hotel.review_score} count={hotel.review_count} />}
              {location && <span style={{ fontSize: '13px', color: t.ink2 }}>{location}</span>}
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '16px' }}>
              <span style={{ fontFamily: t.font, fontSize: '22px', fontWeight: 700, color: t.ink }}>
                {formatPrice(hotel?.min_price)}
              </span>
              {hotel?.min_price ? <span style={{ fontSize: '13px', color: t.ink3 }}>/ đêm</span> : null}
            </div>

            {hotel?.address && (
              <div style={{ fontSize: '13px', color: t.ink2, marginTop: '14px', lineHeight: 1.5 }}>{hotel.address}</div>
            )}

            {(hotel?.property_type || hotel?.accommodation_type) && (
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '16px' }}>
                {[hotel?.accommodation_type, hotel?.property_type].filter(Boolean).map((tag) => (
                  <span key={tag} style={{
                    fontSize: '12px', fontWeight: 500, padding: '5px 12px', borderRadius: t.rPill,
                    background: t.bgSoft, color: t.ink2,
                  }}>
                    {tag}
                  </span>
                ))}
              </div>
            )}

            {hotel?.amenities && hotel.amenities.length > 0 && (
              <div style={{ marginTop: '24px' }}>
                <div style={{ fontFamily: t.font, fontSize: '15px', fontWeight: 700, marginBottom: '10px' }}>
                  Tiện ích nổi bật
                </div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {hotel.amenities.slice(0, 14).map((a, i) => (
                    <span key={i} style={{
                      fontSize: '12px', fontWeight: 500, padding: '5px 12px', borderRadius: t.rPill,
                      background: t.accentSoft, color: t.accentDark,
                    }}>
                      {a.name}
                    </span>
                  ))}
                  {hotel.amenities.length > 14 && (
                    <span style={{ fontSize: '12px', padding: '5px 4px', color: t.ink3 }}>
                      +{hotel.amenities.length - 14} tiện ích khác
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Cột phải: mô tả (cuộn riêng) ── */}
        <div className="no-scrollbar" style={{
          flex: '1 1 44%', minWidth: 0, overflowY: 'auto',
          borderLeft: `1px solid ${t.border}`, padding: '28px 26px',
        }}>
          <div style={{ fontFamily: t.serif, fontSize: '20px', fontWeight: 600, marginBottom: '14px' }}>
            Giới thiệu
          </div>
          {hotel?.description ? (
            <p style={{ fontSize: '14px', lineHeight: 1.85, color: t.ink2, margin: 0, whiteSpace: 'pre-line' }}>
              {hotel.description}
            </p>
          ) : (
            <p style={{ fontSize: '14px', color: t.ink3, margin: 0 }}>
              {loading ? 'Đang tải mô tả…' : 'Chưa có mô tả cho khách sạn này.'}
            </p>
          )}

          {error && <div style={{ color: '#c0392b', fontSize: '13px', marginTop: '16px' }}>{error}</div>}
        </div>
      </div>
    </div>
  );
}
