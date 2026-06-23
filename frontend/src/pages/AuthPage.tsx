import { useState, type CSSProperties, type FormEvent } from 'react';
import { t } from '../styles/theme';
import { useAuth } from '../hooks/useAuth';

type Mode = 'login' | 'register';

export function AuthPage() {
  const { login, register, loading, error, clearError } = useAuth();
  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [showPassword, setShowPassword] = useState(false);

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
      // App.tsx will automatically re-render and navigate away when `user` state updates
    } catch {
      // error is set via context
    }
  };

  const isValid =
    mode === 'login'
      ? username.length >= 1 && password.length >= 1
      : username.length >= 3 && password.length >= 6 && name.length >= 1;

  return (
    <div style={{
      display: 'flex',
      minHeight: '100vh',
      background: t.bg,
      fontFamily: t.font,
    }}>
      {/* Lưng chừng màn hình bên trái: Hình ảnh du lịch truyền cảm hứng (ẩn trên mobile) */}
      <div className="auth-hero" style={{
        flex: 1.2,
        background: `url('https://images.unsplash.com/photo-1542314831-c53cd4b85d05?q=80&w=2070&auto=format&fit=crop') center/cover no-repeat`,
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '60px',
        color: '#fff',
      }}>
        {/* Lớp overlay đen mờ cho ảnh dễ nhìn chữ */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.6) 100%)',
        }} />

        <div style={{ position: 'relative', zIndex: 1 }}>
          <h1 style={{
            fontFamily: t.serif,
            fontSize: '32px',
            fontWeight: 700,
            letterSpacing: '0.02em',
            margin: 0,
          }}>
            VinJourney
          </h1>
        </div>

        <div style={{ position: 'relative', zIndex: 1, maxWidth: 480 }}>
          <h2 style={{
            fontFamily: t.serif,
            fontSize: '48px',
            fontWeight: 600,
            lineHeight: 1.2,
            margin: '0 0 16px',
            textShadow: '0 2px 10px rgba(0,0,0,0.3)',
          }}>
            Khám phá thế giới theo cách riêng của bạn.
          </h2>
          <p style={{
            fontSize: '16px',
            lineHeight: 1.6,
            color: 'rgba(255,255,255,0.9)',
            margin: 0,
          }}>
            VinBot AI sẽ giúp bạn lập kế hoạch, tìm kiếm khách sạn và tạo ra những lịch trình du lịch cá nhân hoá hoàn hảo nhất.
          </p>
        </div>
      </div>

      {/* Nửa bên phải: Form đăng nhập/đăng ký */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '40px 24px',
        background: t.surface,
        position: 'relative',
      }}>
        <div style={{ width: '100%', maxWidth: 400 }}>
          {/* Mobile Header (chỉ hiện khi màn nhỏ, auth-hero bị ẩn) */}
          <div className="auth-mobile-header" style={{
            fontFamily: t.serif,
            fontSize: 28,
            fontWeight: 600,
            color: t.ink,
            textAlign: 'center',
            marginBottom: 32,
            display: 'none',
          }}>
            VinJourney
          </div>

          <div style={{ marginBottom: 32 }}>
            <h2 style={{
              fontFamily: t.font,
              fontSize: 28,
              fontWeight: 700,
              color: t.ink,
              margin: '0 0 8px',
            }}>
              {mode === 'login' ? 'Chào mừng trở lại' : 'Tạo tài khoản mới'}
            </h2>
            <p style={{
              fontFamily: t.font,
              fontSize: 15,
              color: t.ink2,
              margin: 0,
            }}>
              {mode === 'login' 
                ? 'Đăng nhập để xem lịch sử và nhận gợi ý cá nhân hoá.' 
                : 'Tham gia VinJourney ngay hôm nay.'}
            </p>
          </div>

          {/* Tab switcher */}
          <div style={{
            display: 'flex',
            background: t.bgSoft,
            borderRadius: t.rPill,
            padding: 4,
            marginBottom: 32,
          }}>
            {(['login', 'register'] as Mode[]).map(m => (
              <button
                key={m}
                onClick={() => switchMode(m)}
                style={{
                  flex: 1,
                  padding: '10px 0',
                  borderRadius: t.rPill,
                  border: 'none',
                  fontFamily: t.font,
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all .2s',
                  background: mode === m ? t.surface : 'transparent',
                  color: mode === m ? t.ink : t.ink3,
                  boxShadow: mode === m ? '0 2px 8px rgba(28,27,25,0.08)' : 'none',
                }}
              >
                {m === 'login' ? 'Đăng nhập' : 'Đăng ký'}
              </button>
            ))}
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit}>
            {mode === 'register' && (
              <div style={{ marginBottom: 20 }}>
                <label style={labelStyle}>Tên hiển thị</label>
                <input
                  id="auth-name"
                  type="text"
                  placeholder="Ví dụ: Nguyễn Văn A"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  style={inputStyle}
                  autoComplete="name"
                />
              </div>
            )}

            <div style={{ marginBottom: 20 }}>
              <label style={labelStyle}>Tên đăng nhập</label>
              <input
                id="auth-username"
                type="text"
                placeholder="username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                style={inputStyle}
                autoComplete="username"
                autoFocus
              />
            </div>

            <div style={{ marginBottom: 12 }}>
              <label style={labelStyle}>Mật khẩu</label>
              <div style={{ position: 'relative' }}>
                <input
                  id="auth-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder={mode === 'register' ? 'Tối thiểu 6 ký tự' : '••••••••'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  style={{ ...inputStyle, paddingRight: 44 }}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(p => !p)}
                  style={{
                    position: 'absolute',
                    right: 14,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: t.ink3,
                    fontSize: 20,
                    padding: 0,
                    lineHeight: 1,
                  }}
                  tabIndex={-1}
                >
                  {showPassword ? '🙈' : '👁'}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div style={{
                background: '#FEF2F2',
                border: '1px solid #FECACA',
                borderRadius: 12,
                padding: '12px 16px',
                marginTop: 16,
                marginBottom: 8,
                fontFamily: t.font,
                fontSize: 14,
                color: '#B91C1C',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}>
                <span style={{ fontSize: 16 }}>⚠️</span>
                <span>{error}</span>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !isValid}
              style={{
                width: '100%',
                marginTop: 28,
                padding: '16px 0',
                border: 'none',
                borderRadius: t.rPill,
                background: isValid ? t.navy : t.bgSoft,
                color: isValid ? t.onNavy : t.ink3,
                fontFamily: t.font,
                fontSize: 15,
                fontWeight: 600,
                cursor: isValid && !loading ? 'pointer' : 'default',
                transition: 'all .2s',
                opacity: loading ? 0.7 : 1,
              }}
            >
              {loading
                ? '⏳ Đang xử lý...'
                : mode === 'login'
                  ? 'Đăng nhập vào hệ thống'
                  : 'Tạo tài khoản ngay'}
            </button>
          </form>
        </div>
      </div>

      <style>{`
        @media (max-width: 900px) {
          .auth-hero { display: none !important; }
          .auth-mobile-header { display: block !important; }
        }
      `}</style>
    </div>
  );
}

// ── Shared styles ────────────────────────────────────────────────────────────

const labelStyle: CSSProperties = {
  display: 'block',
  fontFamily: t.font,
  fontSize: 14,
  fontWeight: 600,
  color: t.ink,
  marginBottom: 8,
};

const inputStyle: CSSProperties = {
  width: '100%',
  padding: '14px 16px',
  border: `1.5px solid ${t.borderStrong}`,
  borderRadius: 12,
  fontFamily: t.font,
  fontSize: 15,
  color: t.ink,
  background: t.bg,
  outline: 'none',
  transition: 'border-color .2s, box-shadow .2s',
  boxSizing: 'border-box',
};
