// AuthModal — modal đăng nhập / đăng ký, editorial-style matching VinJourney theme.

import { useState, type CSSProperties, type FormEvent } from 'react';
import { t } from '../../styles/theme';
import { useAuth } from '../../hooks/useAuth';

type Mode = 'login' | 'register';

export function AuthModal({ onClose }: { onClose: () => void }) {
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
      onClose();
    } catch {
      // error is set via context
    }
  };

  const isValid =
    mode === 'login'
      ? username.length >= 1 && password.length >= 1
      : username.length >= 3 && password.length >= 6 && name.length >= 1;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(28,27,25,0.45)',
          backdropFilter: 'blur(6px)',
          zIndex: 9998,
          animation: 'authFadeIn .25s ease',
        }}
      />

      {/* Modal */}
      <div style={{
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 9999,
        width: 420,
        maxWidth: 'calc(100vw - 32px)',
        background: t.surface,
        borderRadius: t.rPanel,
        boxShadow: t.shadowLg,
        overflow: 'hidden',
        animation: 'authSlideUp .3s cubic-bezier(.16,1,.3,1)',
      }}>
        {/* Header accent bar */}
        <div style={{
          height: 4,
          background: `linear-gradient(90deg, ${t.accent}, ${t.accentDark})`,
        }} />

        <div style={{ padding: '36px 36px 32px' }}>
          {/* Logo */}
          <div style={{
            fontFamily: t.serif,
            fontSize: 22,
            fontWeight: 600,
            color: t.ink,
            textAlign: 'center',
            marginBottom: 4,
          }}>
            VinJourney
          </div>
          <p style={{
            fontFamily: t.font,
            fontSize: 13,
            color: t.ink3,
            textAlign: 'center',
            marginBottom: 28,
          }}>
            {mode === 'login' ? 'Đăng nhập để tiếp tục trải nghiệm' : 'Tạo tài khoản mới'}
          </p>

          {/* Tab switcher */}
          <div style={{
            display: 'flex',
            background: t.bgSoft,
            borderRadius: t.rPill,
            padding: 3,
            marginBottom: 24,
          }}>
            {(['login', 'register'] as Mode[]).map(m => (
              <button
                key={m}
                onClick={() => switchMode(m)}
                style={{
                  flex: 1,
                  padding: '9px 0',
                  borderRadius: t.rPill,
                  border: 'none',
                  fontFamily: t.font,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all .2s',
                  background: mode === m ? t.surface : 'transparent',
                  color: mode === m ? t.ink : t.ink3,
                  boxShadow: mode === m ? '0 1px 4px rgba(28,27,25,0.1)' : 'none',
                }}
              >
                {m === 'login' ? 'Đăng nhập' : 'Đăng ký'}
              </button>
            ))}
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit}>
            {mode === 'register' && (
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Tên hiển thị</label>
                <input
                  id="auth-name"
                  type="text"
                  placeholder="Nguyễn Văn A"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  style={inputStyle}
                  autoComplete="name"
                />
              </div>
            )}

            <div style={{ marginBottom: 16 }}>
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

            <div style={{ marginBottom: 8 }}>
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
                    right: 12,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: t.ink3,
                    fontSize: 18,
                    padding: 0,
                    lineHeight: 1,
                  }}
                  tabIndex={-1}
                  aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
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
                borderRadius: 8,
                padding: '10px 14px',
                marginTop: 12,
                marginBottom: 4,
                fontFamily: t.font,
                fontSize: 13,
                color: '#B91C1C',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}>
                <span>⚠️</span>
                <span>{error}</span>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !isValid}
              style={{
                width: '100%',
                marginTop: 20,
                padding: '13px 0',
                border: 'none',
                borderRadius: t.rPill,
                background: isValid ? t.navy : t.bgSoft,
                color: isValid ? t.onNavy : t.ink3,
                fontFamily: t.font,
                fontSize: 14,
                fontWeight: 600,
                cursor: isValid && !loading ? 'pointer' : 'default',
                transition: 'all .2s',
                opacity: loading ? 0.7 : 1,
              }}
            >
              {loading
                ? '⏳ Đang xử lý...'
                : mode === 'login'
                  ? 'Đăng nhập'
                  : 'Tạo tài khoản'}
            </button>
          </form>

          {/* Footer hint */}
          <p style={{
            fontFamily: t.font,
            fontSize: 12,
            color: t.ink3,
            textAlign: 'center',
            marginTop: 20,
            marginBottom: 0,
          }}>
            {mode === 'login'
              ? <>Chưa có tài khoản?{' '}
                <span onClick={() => switchMode('register')} style={linkStyle}>Đăng ký ngay</span>
              </>
              : <>Đã có tài khoản?{' '}
                <span onClick={() => switchMode('login')} style={linkStyle}>Đăng nhập</span>
              </>}
          </p>
        </div>

        {/* Close button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: 16,
            right: 16,
            background: 'none',
            border: 'none',
            fontSize: 20,
            color: t.ink3,
            cursor: 'pointer',
            lineHeight: 1,
            padding: 4,
            borderRadius: 6,
            transition: 'color .15s',
          }}
          aria-label="Đóng"
          onMouseEnter={e => (e.currentTarget.style.color = t.ink)}
          onMouseLeave={e => (e.currentTarget.style.color = t.ink3)}
        >
          ✕
        </button>
      </div>

      {/* Animation keyframes */}
      <style>{`
        @keyframes authFadeIn {
          from { opacity: 0 }
          to { opacity: 1 }
        }
        @keyframes authSlideUp {
          from { opacity: 0; transform: translate(-50%, -46%) }
          to { opacity: 1; transform: translate(-50%, -50%) }
        }
      `}</style>
    </>
  );
}

// ── Shared styles ────────────────────────────────────────────────────────────

const labelStyle: CSSProperties = {
  display: 'block',
  fontFamily: t.font,
  fontSize: 13,
  fontWeight: 500,
  color: t.ink2,
  marginBottom: 6,
};

const inputStyle: CSSProperties = {
  width: '100%',
  padding: '11px 14px',
  border: `1px solid ${t.border}`,
  borderRadius: 10,
  fontFamily: t.font,
  fontSize: 14,
  color: t.ink,
  background: t.bg,
  outline: 'none',
  transition: 'border-color .2s, box-shadow .2s',
  boxSizing: 'border-box',
};

const linkStyle: CSSProperties = {
  color: t.accent,
  fontWeight: 600,
  cursor: 'pointer',
  textDecoration: 'underline',
};
