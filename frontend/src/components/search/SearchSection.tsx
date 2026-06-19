import { t } from '../../styles/theme';

export function SearchSection() {
  return (
    <div style={{
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
          <input type="text" placeholder="Phú Quốc, Đà Nẵng, Hội An..." style={inputStyle} />
        </FieldGroup>
        <FieldGroup label="Ngày đi">
          <input type="date" style={inputStyle} />
        </FieldGroup>
        <FieldGroup label="Số người">
          <select style={inputStyle}>
            <option>2 người lớn</option>
            <option>1 người lớn</option>
            <option>2 + 1 trẻ em</option>
            <option>Nhóm (5+)</option>
          </select>
        </FieldGroup>
        <button style={{
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
          onMouseEnter={e => (e.currentTarget.style.background = t.navyHover)}
          onMouseLeave={e => (e.currentTarget.style.background = t.navy)}
        >
          Tìm kiếm
        </button>
      </div>
    </div>
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
