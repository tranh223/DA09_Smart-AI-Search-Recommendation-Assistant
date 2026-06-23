import { useRef, useState, type CSSProperties, type FormEvent, type MouseEvent } from 'react';
import { t } from '../styles/theme';
import { useAuth } from '../hooks/useAuth';
import heroImage from '../../asset/login-bg.jpg';

type Mode = 'login' | 'register';

// Ảnh nền: view biển từ trên cao (đã xoay ngang) — nhiều chiều sâu, đẹp khi parallax.
const HERO_IMAGE = heroImage;

export function AuthPage() {
  const { login, register, loading, error, clearError } = useAuth();
  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Refs cho hiệu ứng parallax + vệt sáng (ghi thẳng style, không re-render).
  const bgRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const sheenRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);
  const targetRef = useRef({ x: 0, y: 0 });

  const applyParallax = () => {
    rafRef.current = 0;
    const { x, y } = targetRef.current;
    if (bgRef.current) {
      // Nền dịch NGƯỢC hướng chuột để tạo chiều sâu.
      bgRef.current.style.transform = `scale(1.12) translate3d(${x * -26}px, ${y * -26}px, 0)`;
    }
    if (panelRef.current) {
      // Panel dịch nhẹ THEO hướng chuột (ít hơn) → lớp lang, nổi khối.
      panelRef.current.style.transform = `translate3d(${x * 10}px, ${y * 10}px, 0)`;
    }
  };

  const handleRootMove = (e: MouseEvent<HTMLDivElement>) => {
    targetRef.current = {
      x: e.clientX / window.innerWidth - 0.5,
      y: e.clientY / window.innerHeight - 0.5,
    };
    if (!rafRef.current) rafRef.current = requestAnimationFrame(applyParallax);
  };

  const handleGlassMove = (e: MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - r.left;
    const my = e.clientY - r.top;
    if (sheenRef.current) {
      sheenRef.current.style.background =
        `radial-gradient(420px circle at ${mx}px ${my}px, rgba(255,255,255,0.18), rgba(255,255,255,0) 62%)`;
      sheenRef.current.style.opacity = '1';
    }
  };
  const handleGlassLeave = () => {
    if (sheenRef.current) sheenRef.current.style.opacity = '0';
  };

  const switchMode = (m: Mode) => {
    setMode(m);
    clearError();
    setUsername('');
    setPassword('');
    setName('');
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      if (mode === 'login') {
        await login(username, password);
      } else {
        await register(username, password, name);
      }
      // App.tsx tự re-render & điều hướng khi `user` cập nhật.
    } catch {
      // error đã set qua context
    }
  };

  const isValid =
    mode === 'login'
      ? username.length >= 1 && password.length >= 1
      : username.length >= 3 && password.length >= 6 && name.length >= 1;

  return (
    <div
      onMouseMove={handleRootMove}
      style={{
        position: 'relative',
        minHeight: '100vh',
        overflow: 'hidden',
        fontFamily: t.font,
        background: '#0c0b0a',
      }}
    >
      {/* ── Lớp ảnh nền (parallax) ─────────────────────────────────────────── */}
      <div
        ref={bgRef}
        style={{
          position: 'absolute',
          inset: '-6%',
          background: `url('${HERO_IMAGE}') center/cover no-repeat`,
          transform: 'scale(1.12)',
          transition: 'transform .5s cubic-bezier(.22,.61,.36,1)',
          willChange: 'transform',
        }}
      />
      {/* Overlay tăng chiều sâu + giữ chữ dễ đọc, tối dần về bên phải */}
      <div style={{
        position: 'absolute', inset: 0,
        background:
          'linear-gradient(105deg, rgba(12,11,10,0.30) 0%, rgba(12,11,10,0.45) 42%, rgba(12,11,10,0.72) 100%)',
      }} />
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(120% 120% at 15% 20%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.45) 100%)',
      }} />

      {/* ── Nội dung ───────────────────────────────────────────────────────── */}
      <div className="auth-content" style={{
        position: 'relative',
        zIndex: 1,
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 40,
        padding: '48px clamp(40px, 7vw, 110px)',
        boxSizing: 'border-box',
      }}>
        {/* Cột trái: editorial (ẩn trên mobile) */}
        <div className="auth-left" style={{ flex: 1, maxWidth: 520, color: '#fff' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 'clamp(40px, 12vh, 120px)' }}>
            <span style={{
              width: 7, height: 7, borderRadius: '50%',
              background: t.accent, boxShadow: '0 0 0 4px rgba(14,110,99,0.30)',
            }} />
            <span style={{ fontFamily: t.serif, fontSize: 24, fontWeight: 600, letterSpacing: '0.05em' }}>
              VinJourney
            </span>
          </div>

          <h1 style={{
            fontFamily: t.serif,
            fontSize: 'clamp(40px, 5vw, 60px)',
            fontWeight: 500,
            lineHeight: 1.12,
            letterSpacing: '0.005em',
            margin: '0 0 22px',
            textShadow: '0 4px 30px rgba(0,0,0,0.45)',
          }}>
            Mỗi hành trình<br />một câu chuyện riêng.
          </h1>
          <p style={{
            fontSize: 17,
            lineHeight: 1.75,
            color: 'rgba(255,255,255,0.82)',
            margin: 0,
            maxWidth: 440,
            textShadow: '0 2px 16px rgba(0,0,0,0.4)',
          }}>
            Để VinBot AI lắng nghe sở thích của bạn và kiến tạo những trải nghiệm
            nghỉ dưỡng được cá nhân hoá đến từng chi tiết.
          </p>

          <div style={{
            marginTop: 44, paddingTop: 24,
            borderTop: '1px solid rgba(255,255,255,0.20)',
            display: 'flex', alignItems: 'center', gap: 14,
            fontSize: 13.5, letterSpacing: '0.04em', color: 'rgba(255,255,255,0.74)',
          }}>
            <span>Gợi ý khách sạn bằng AI</span>
            <span style={{ opacity: 0.5 }}>•</span>
            <span>Lịch trình cá nhân hoá</span>
          </div>
        </div>

        {/* Cột phải: panel kính mờ trong suốt (parallax wrapper) */}
        <div ref={panelRef} className="auth-panel-wrap" style={{
          flexShrink: 0,
          willChange: 'transform',
          transition: 'transform .5s cubic-bezier(.22,.61,.36,1)',
        }}>
          <div
            onMouseMove={handleGlassMove}
            onMouseLeave={handleGlassLeave}
            className="auth-glass"
            style={{
              position: 'relative',
              width: 'min(420px, 86vw)',
              padding: '40px 38px',
              borderRadius: 24,
              overflow: 'hidden',
              // Độ trong suốt tăng/giảm dần (đậm hơn về phía dưới).
              background:
                'linear-gradient(155deg, rgba(20,21,24,0.42) 0%, rgba(16,17,20,0.58) 55%, rgba(14,15,17,0.66) 100%)',
              backdropFilter: 'blur(22px) saturate(135%)',
              WebkitBackdropFilter: 'blur(22px) saturate(135%)',
              border: '1px solid rgba(255,255,255,0.16)',
              boxShadow: '0 30px 80px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.18)',
              color: '#fff',
            }}
          >
            {/* Vệt sáng đi theo chuột */}
            <div ref={sheenRef} style={{
              position: 'absolute', inset: 0, pointerEvents: 'none',
              opacity: 0, transition: 'opacity .35s ease', mixBlendMode: 'soft-light',
            }} />

            <div style={{ position: 'relative' }}>
              {/* Brand mobile */}
              <div className="auth-mobile-header" style={{
                fontFamily: t.serif, fontSize: 24, fontWeight: 600, letterSpacing: '0.04em',
                color: '#fff', textAlign: 'center', marginBottom: 28, display: 'none',
              }}>
                VinJourney
              </div>

              <div style={{ marginBottom: 26 }}>
                <h2 style={{
                  fontFamily: t.serif, fontSize: 30, fontWeight: 600,
                  letterSpacing: '0.005em', color: '#fff', margin: '0 0 8px',
                }}>
                  {mode === 'login' ? 'Chào mừng trở lại' : 'Tạo tài khoản mới'}
                </h2>
                <p style={{
                  fontFamily: t.font, fontSize: 14.5, lineHeight: 1.6,
                  color: 'rgba(255,255,255,0.68)', margin: 0,
                }}>
                  {mode === 'login'
                    ? 'Đăng nhập để lưu lịch sử và nhận gợi ý riêng cho bạn.'
                    : 'Chỉ một bước để bắt đầu hành trình cùng VinJourney.'}
                </p>
              </div>

              {/* Tab switcher */}
              <div style={{
                display: 'flex', background: 'rgba(255,255,255,0.08)',
                borderRadius: t.rPill, padding: 4, marginBottom: 26,
                border: '1px solid rgba(255,255,255,0.10)',
              }}>
                {(['login', 'register'] as Mode[]).map(m => (
                  <button
                    key={m}
                    onClick={() => switchMode(m)}
                    style={{
                      flex: 1, padding: '10px 0', borderRadius: t.rPill, border: 'none',
                      fontFamily: t.font, fontSize: 14, fontWeight: 600, letterSpacing: '0.01em',
                      cursor: 'pointer', transition: 'all .25s ease',
                      background: mode === m ? 'rgba(255,255,255,0.95)' : 'transparent',
                      color: mode === m ? t.ink : 'rgba(255,255,255,0.62)',
                      boxShadow: mode === m ? '0 2px 12px rgba(0,0,0,0.25)' : 'none',
                    }}
                  >
                    {m === 'login' ? 'Đăng nhập' : 'Đăng ký'}
                  </button>
                ))}
              </div>

              <form onSubmit={handleSubmit}>
                {mode === 'register' && (
                  <div style={{ marginBottom: 16 }}>
                    <label style={labelStyle}>Tên hiển thị</label>
                    <input
                      id="auth-name" className="auth-input" type="text"
                      placeholder="Ví dụ: Nguyễn Văn A"
                      value={name} onChange={e => setName(e.target.value)}
                      style={inputStyle} autoComplete="name"
                    />
                  </div>
                )}

                <div style={{ marginBottom: 16 }}>
                  <label style={labelStyle}>Tên đăng nhập</label>
                  <input
                    id="auth-username" className="auth-input" type="text"
                    placeholder="username"
                    value={username} onChange={e => setUsername(e.target.value)}
                    style={inputStyle} autoComplete="username" autoFocus
                  />
                </div>

                <div style={{ marginBottom: 12 }}>
                  <label style={labelStyle}>Mật khẩu</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      id="auth-password" className="auth-input"
                      type={showPassword ? 'text' : 'password'}
                      placeholder={mode === 'register' ? 'Tối thiểu 6 ký tự' : '••••••••'}
                      value={password} onChange={e => setPassword(e.target.value)}
                      style={{ ...inputStyle, paddingRight: 46 }}
                      autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                    />
                    <button
                      type="button" onClick={() => setShowPassword(p => !p)}
                      aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                      style={{
                        position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'rgba(255,255,255,0.55)', display: 'flex',
                        alignItems: 'center', justifyContent: 'center', padding: 6, lineHeight: 0,
                      }}
                      tabIndex={-1}
                    >
                      {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                    </button>
                  </div>
                </div>

                {error && (
                  <div style={{
                    background: 'rgba(190,45,35,0.18)',
                    border: '1px solid rgba(248,150,140,0.32)',
                    borderRadius: 12, padding: '11px 14px', marginTop: 16, marginBottom: 4,
                    fontFamily: t.font, fontSize: 13.5, lineHeight: 1.5, color: '#FCA5A5',
                    display: 'flex', alignItems: 'flex-start', gap: 10,
                  }}>
                    <AlertIcon />
                    <span>{error}</span>
                  </div>
                )}

                <button
                  type="submit" className="auth-submit"
                  disabled={loading || !isValid}
                  style={{
                    width: '100%', marginTop: 24, padding: '15px 0', border: 'none',
                    borderRadius: t.rPill,
                    background: isValid ? '#fff' : 'rgba(255,255,255,0.14)',
                    color: isValid ? t.ink : 'rgba(255,255,255,0.42)',
                    fontFamily: t.font, fontSize: 15, fontWeight: 600, letterSpacing: '0.02em',
                    cursor: isValid && !loading ? 'pointer' : 'default',
                    transition: 'background .25s ease, transform .12s ease, box-shadow .25s ease',
                    opacity: loading ? 0.8 : 1,
                    boxShadow: isValid ? '0 8px 26px rgba(0,0,0,0.30)' : 'none',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                  }}
                >
                  {loading && <Spinner />}
                  {loading ? 'Đang xử lý…' : mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}
                </button>
              </form>

              <p style={{
                textAlign: 'center', marginTop: 24, fontSize: 12.5,
                color: 'rgba(255,255,255,0.48)', letterSpacing: '0.01em',
              }}>
                Bằng việc tiếp tục, bạn đồng ý với Điều khoản &amp; Chính sách của VinJourney.
              </p>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 900px) {
          .auth-left { display: none !important; }
          .auth-content { justify-content: center !important; }
          .auth-mobile-header { display: block !important; }
        }
        @keyframes auth-spin { to { transform: rotate(360deg); } }
        .auth-input::placeholder { color: rgba(255,255,255,0.42); }
        .auth-input:focus {
          border-color: ${t.accent} !important;
          background: rgba(255,255,255,0.12) !important;
          box-shadow: 0 0 0 4px rgba(14,110,99,0.28) !important;
        }
        .auth-submit:not(:disabled):hover {
          background: rgba(255,255,255,0.92) !important;
          box-shadow: 0 12px 34px rgba(0,0,0,0.38) !important;
        }
        .auth-submit:not(:disabled):active { transform: translateY(1px); }
        @media (prefers-reduced-motion: reduce) {
          .auth-content ~ *, [style*="willChange"] { transition: none !important; }
        }
      `}</style>
    </div>
  );
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function EyeIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.9 4.24A9.1 9.1 0 0 1 12 4c6.5 0 10 7 10 7a17.9 17.9 0 0 1-3.3 4.13M6.6 6.6A17.8 17.8 0 0 0 2 11s3.5 7 10 7a9.1 9.1 0 0 0 4.4-1.1" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
      <path d="m2 2 20 20" />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0, marginTop: 1 }}
      stroke="#FCA5A5" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v4M12 16h.01" />
    </svg>
  );
}

function Spinner() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      style={{ animation: 'auth-spin .7s linear infinite' }}>
      <circle cx="12" cy="12" r="9" stroke="rgba(28,27,25,0.25)" strokeWidth="2.5" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke={t.ink} strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

// ── Shared styles ────────────────────────────────────────────────────────────

const labelStyle: CSSProperties = {
  display: 'block',
  fontFamily: t.font,
  fontSize: 11.5,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: 'rgba(255,255,255,0.62)',
  marginBottom: 8,
};

const inputStyle: CSSProperties = {
  width: '100%',
  padding: '13px 15px',
  border: '1.5px solid rgba(255,255,255,0.16)',
  borderRadius: 12,
  fontFamily: t.font,
  fontSize: 15,
  color: '#fff',
  background: 'rgba(255,255,255,0.07)',
  outline: 'none',
  transition: 'border-color .2s, box-shadow .2s, background .2s',
  boxSizing: 'border-box',
};
