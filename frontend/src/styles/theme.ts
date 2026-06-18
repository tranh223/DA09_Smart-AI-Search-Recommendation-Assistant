// Design tokens — phong cách editorial cao cấp: nền kem ấm, tiêu đề serif thanh
// lịch, ảnh thật cỡ lớn, accent teal trầm, viền hairline, shadow rất nhẹ.

export const t = {
  // Nền & bề mặt
  bg: '#FAF8F4', // kem ấm
  bgSoft: '#F0ECE4',
  surface: '#FFFFFF',

  // Mực chữ (warm near-black)
  ink: '#1C1B19',
  ink2: '#6E6A63',
  ink3: '#A8A29A',

  // Primary (near-black, kiểu nút đen editorial) — giữ tên "navy" để khỏi đổi import
  navy: '#1C1B19',
  navyHover: '#3B3833',
  onNavy: '#FFFFFF',

  // Accent — teal trầm, tinh tế
  accent: '#0E6E63',
  accentDark: '#0A544B',
  accentSoft: '#E7F0EE',

  // Viền & shadow
  border: '#ECE7DE',
  borderStrong: '#DCD5C8',
  shadow: '0 12px 40px rgba(28,27,25,0.10)',
  shadowSoft: '0 4px 18px rgba(28,27,25,0.06)',
  shadowLg: '0 28px 70px rgba(28,27,25,0.22)',

  // Bo góc
  rPill: '999px',
  rCard: '16px',
  rBtn: '10px',
  rPanel: '20px',

  // Chữ
  font: "'Be Vietnam Pro', sans-serif",
  serif: "'Playfair Display', Georgia, serif",
} as const;

export const headingFont = t.serif;
