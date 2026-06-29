import { useState } from 'react';
import { t } from '../../styles/theme';

export interface SearchValues {
  destination: string;
  starRatingMin?: number;
}

export function SearchSection({ onSearch }: { onSearch?: (values: SearchValues) => void }) {
  const [destination, setDestination] = useState('');
  const [starRatingMin, setStarRatingMin] = useState('');

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch?.({
      destination: destination.trim(),
      starRatingMin: starRatingMin ? Number(starRatingMin) : undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit} style={{
      background: t.surface,
      border: `1px solid ${t.border}`,
      borderRadius: t.rPanel,
      padding: '26px 32px',
      margin: '-52px 64px 0',
      position: 'relative',
      zIndex: 10,
      boxShadow: t.shadow,
    }}>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr auto', gap: '20px', alignItems: 'end' }}>
        <FieldGroup label="Điểm đến">
          <input
            type="text"
            placeholder="Phú Quốc, Đà Nẵng, Hội An..."
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            style={inputStyle}
          />
        </FieldGroup>
        <FieldGroup label="Hạng sao">
          <select style={inputStyle} value={starRatingMin} onChange={(e) => setStarRatingMin(e.target.value)}>
            <option value="">Tất cả</option>
            <option value="3">3 sao trở lên</option>
            <option value="4">4 sao trở lên</option>
            <option value="5">5 sao</option>
          </select>
        </FieldGroup>
        <button
          type="submit"
          style={{
            background: t.navy,
            color: t.onNavy,
            fontFamily: t.font,
            fontSize: '15px',
            fontWeight: 600,
            padding: '13px 32px',
            borderRadius: t.rPill,
            border: 'none',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            transition: 'background .15s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = t.navyHover)}
          onMouseLeave={(e) => (e.currentTarget.style.background = t.navy)}
        >
          Tìm kiếm
        </button>
      </div>
    </form>
  );
}

function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <label style={{
        display: 'block', fontFamily: t.font, fontSize: '11px', fontWeight: 600,
        letterSpacing: '0.08em', textTransform: 'uppercase', color: t.ink3, marginBottom: '8px',
      }}>
        {label}
      </label>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '11px 0',
  border: 'none',
  borderBottom: `1px solid ${t.border}`,
  borderRadius: 0,
  fontFamily: t.font,
  fontSize: '15px',
  color: t.ink,
  background: 'transparent',
  outline: 'none',
};
