export function SearchSection() {
  return (
    <div style={{
      background: 'white',
      border: '2.5px solid #D42B2B',
      borderRadius: '20px',
      padding: '22px 30px',
      margin: '28px 40px 0',
      position: 'relative',
      zIndex: 10,
      boxShadow: '5px 5px 0 #F5DADA',
    }}>
      <div style={{
        fontFamily: "'Pangolin', cursive",
        fontSize: '17px',
        color: '#D42B2B',
        fontWeight: 600,
        marginBottom: '12px',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
      }}>
        <svg width="17" height="17" viewBox="0 0 18 18" fill="none">
          <path d="M8 2 Q14 2 14 8 Q14 14 8 14 Q2 14 2 8 Q2 2 8 2Z" stroke="#D42B2B" strokeWidth="2" fill="none"/>
          <path d="M12 12 L16 16" stroke="#D42B2B" strokeWidth="2.5" strokeLinecap="round"/>
        </svg>
        Tìm kiếm hành trình của bạn ✏️
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr auto', gap: '12px', alignItems: 'end' }}>
        <FieldGroup label="📍 Điểm đến">
          <input type="text" placeholder="Phú Quốc, Đà Nẵng, Hội An..." style={inputStyle} />
        </FieldGroup>
        <FieldGroup label="📅 Ngày đi">
          <input type="date" style={inputStyle} />
        </FieldGroup>
        <FieldGroup label="👥 Số người">
          <select style={inputStyle}>
            <option>2 người lớn</option>
            <option>1 người lớn</option>
            <option>2 + 1 trẻ em</option>
            <option>Nhóm (5+)</option>
          </select>
        </FieldGroup>
        <button style={{
          background: '#D42B2B',
          color: 'white',
          fontFamily: "'Pangolin', cursive",
          fontSize: '19px',
          padding: '10px 26px',
          borderRadius: '10px',
          border: '2.5px solid #A01E1E',
          cursor: 'pointer',
          boxShadow: '3px 3px 0 #A01E1E',
          transition: 'transform .1s, box-shadow .1s',
          whiteSpace: 'nowrap',
        }}
          onMouseEnter={e => { e.currentTarget.style.transform = 'translate(-1px,-1px)'; e.currentTarget.style.boxShadow = '4px 4px 0 #A01E1E'; }}
          onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = '3px 3px 0 #A01E1E'; }}
        >
          🔍 Tìm kiếm
        </button>
      </div>
    </div>
  );
}

function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label style={{ display: 'block', fontFamily: "'Pangolin', cursive", fontSize: '14px', color: '#5A3A3A', marginBottom: '5px' }}>
        {label}
      </label>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 14px',
  border: '2px solid #F5DADA',
  borderRadius: '10px',
  fontFamily: "'Be Vietnam Pro', sans-serif",
  fontSize: '14px',
  color: '#2A1A1A',
  background: '#FFFDF8',
  outline: 'none',
};
