interface HeroSectionProps {
  onOpenChat: () => void;
}

export function HeroSection({ onOpenChat }: HeroSectionProps) {
  return (
    <>
      <section style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        minHeight: '500px',
        padding: '0 40px',
        alignItems: 'center',
        background: '#FFFDF8',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* warm blob */}
        <div style={{
          position: 'absolute', top: '20px', right: 0, width: '58%', height: '115%',
          background: '#FFF5EC', borderRadius: '60% 0 0 50%',
          borderLeft: '2px dashed #D42B2B', opacity: 0.55, zIndex: 0,
        }} />

        {/* Hero text */}
        <div style={{ position: 'relative', zIndex: 2, padding: '50px 0' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '8px',
            background: '#F5DADA', color: '#A01E1E',
            fontFamily: "'Pangolin', cursive", fontSize: '15px',
            padding: '5px 16px', borderRadius: '99px',
            marginBottom: '18px', border: '1.5px solid #D42B2B',
          }}>
            ✦ Khám phá Việt Nam cùng Vingroup
          </div>
          <h1 style={{
            fontFamily: "'Baloo 2', sans-serif", fontSize: '58px', fontWeight: 700,
            lineHeight: 1.1, color: '#2A1A1A', marginBottom: '16px', margin: '0 0 16px',
          }}>
            Mỗi chuyến đi<br />là một{' '}
            <span style={{ color: '#D42B2B', position: 'relative', display: 'inline-block' }}>
              kỷ niệm
              <span style={{
                position: 'absolute', bottom: '4px', left: 0, right: 0,
                height: '4px', background: '#D42B2B', borderRadius: '99px', opacity: 0.35,
              }} />
            </span>
            <br />đáng nhớ!
          </h1>
          <p style={{
            fontSize: '15px', color: '#5A3A3A', lineHeight: 1.75,
            maxWidth: '370px', marginBottom: '30px',
            fontFamily: "'Be Vietnam Pro', sans-serif",
          }}>
            Trải nghiệm những điểm đến tuyệt vời nhất Việt Nam — từ biển xanh Phú Quốc đến phố cổ Hội An — với dịch vụ 5 sao của Vingroup.
          </p>
          <div style={{ display: 'flex', gap: '14px', alignItems: 'center', flexWrap: 'wrap' }}>
            <a href="#" style={{
              background: '#D42B2B', color: 'white',
              fontFamily: "'Pangolin', cursive", fontSize: '19px',
              padding: '12px 28px', borderRadius: '12px',
              border: '2.5px solid #A01E1E', cursor: 'pointer',
              boxShadow: '4px 4px 0 #A01E1E',
              transition: 'transform .15s, box-shadow .15s',
              textDecoration: 'none', display: 'inline-block',
              transform: 'rotate(-1deg)',
            }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'rotate(-1deg) translate(-2px,-2px)'; e.currentTarget.style.boxShadow = '6px 6px 0 #A01E1E'; }}
              onMouseLeave={e => { e.currentTarget.style.transform = 'rotate(-1deg)'; e.currentTarget.style.boxShadow = '4px 4px 0 #A01E1E'; }}
            >
              🗺 Khám phá ngay
            </a>
            <a href="#" style={{
              fontFamily: "'Pangolin', cursive", fontSize: '18px',
              color: '#D42B2B', padding: '12px 22px', borderRadius: '12px',
              border: '2px dashed #D42B2B', background: 'transparent',
              cursor: 'pointer', textDecoration: 'none', display: 'inline-block',
              transition: 'background .15s',
            }}
              onMouseEnter={e => (e.currentTarget.style.background = '#FDF3F3')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              Xem video ↗
            </a>
          </div>

          {/* VinBot Teaser Card */}
          <div
            onClick={onOpenChat}
            style={{
              marginTop: '28px',
              background: 'white',
              border: '2px dashed #D42B2B',
              borderRadius: '16px',
              padding: '14px 18px',
              boxShadow: '4px 4px 0 #F5DADA',
              cursor: 'pointer',
              transform: 'rotate(-0.5deg)',
              transition: 'transform .15s, box-shadow .15s',
              maxWidth: '380px',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.transform = 'rotate(0deg) translateY(-2px)'; (e.currentTarget as HTMLDivElement).style.boxShadow = '6px 6px 0 #F5DADA'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.transform = 'rotate(-0.5deg)'; (e.currentTarget as HTMLDivElement).style.boxShadow = '4px 4px 0 #F5DADA'; }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
              <VinBotAvatarSmall />
              <span style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '15px', fontWeight: 700, color: '#2A1A1A' }}>
                Chưa biết đi đâu? Hỏi <span style={{ color: '#D42B2B' }}>VinBot</span> ngay! ✦
              </span>
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {['🌊 Biển đẹp cuối tuần', '👨‍👩‍👧‍👦 Gia đình 4 người', '💰 Dưới 3 triệu'].map(chip => (
                <span key={chip} style={{
                  fontFamily: "'Pangolin', cursive", fontSize: '13px',
                  color: '#D42B2B', border: '1.5px dashed #D42B2B',
                  borderRadius: '99px', padding: '3px 12px',
                  background: '#FDF3F3',
                }}>
                  {chip}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Hero art */}
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '40px 0' }}>
          <HeroArtSvg />
        </div>
      </section>
    </>
  );
}

function VinBotAvatarSmall() {
  return (
    <svg width="36" height="36" viewBox="0 0 48 48" fill="none">
      <circle cx="24" cy="24" r="22" fill="#FDF3F3" stroke="#D42B2B" strokeWidth="2.5"/>
      <circle cx="17" cy="21" r="2.5" fill="#D42B2B" opacity="0.85"/>
      <circle cx="31" cy="21" r="2.5" fill="#D42B2B" opacity="0.85"/>
      <path d="M16 31 Q24 38 32 31" stroke="#D42B2B" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
      <ellipse cx="13" cy="27" rx="4" ry="2.5" fill="#D42B2B" opacity="0.18"/>
      <ellipse cx="35" cy="27" rx="4" ry="2.5" fill="#D42B2B" opacity="0.18"/>
      <path d="M38 10 L39.2 7 L40.5 10 L43.5 11.2 L40.5 12.4 L39.2 15.5 L38 12.4 L35 11.2Z" fill="#D42B2B" opacity="0.65"/>
    </svg>
  );
}

function HeroArtSvg() {
  return (
    <svg width="360" height="330" viewBox="0 0 360 330" fill="none" xmlns="http://www.w3.org/2000/svg">
      <ellipse cx="180" cy="165" rx="158" ry="148" fill="#FFF5EC" opacity="0.65"/>
      <circle cx="278" cy="68" r="28" fill="#D42B2B" opacity="0.13"/>
      <circle cx="278" cy="68" r="19" fill="#D42B2B" opacity="0.22"/>
      <circle cx="278" cy="68" r="11" fill="#D42B2B" opacity="0.48"/>
      <g stroke="#D42B2B" strokeWidth="2" strokeLinecap="round" opacity="0.35">
        <line x1="278" y1="38" x2="278" y2="31"/><line x1="299" y1="47" x2="305" y2="41"/>
        <line x1="308" y1="68" x2="315" y2="68"/><line x1="299" y1="89" x2="305" y2="95"/>
        <line x1="257" y1="47" x2="251" y2="41"/><line x1="248" y1="68" x2="241" y2="68"/>
      </g>
      <path d="M20 235 L78 118 L136 235Z" fill="#D42B2B" opacity="0.11" stroke="#D42B2B" strokeWidth="2" strokeLinejoin="round"/>
      <path d="M98 235 L168 98 L238 235Z" fill="#D42B2B" opacity="0.17" stroke="#D42B2B" strokeWidth="2.5" strokeLinejoin="round"/>
      <path d="M198 235 L247 158 L296 235Z" fill="#D42B2B" opacity="0.09" stroke="#D42B2B" strokeWidth="2" strokeLinejoin="round"/>
      <path d="M78 118 L93 147 L63 147Z" fill="white" opacity="0.9"/>
      <path d="M168 98 L187 137 L149 137Z" fill="white" opacity="0.9"/>
      <path d="M0 235 Q38 226 78 235 Q118 244 158 235 Q198 226 238 235 Q278 244 318 235 Q338 231 360 235 L360 295 L0 295Z" fill="#D42B2B" opacity="0.07"/>
      <path d="M0 250 Q48 243 96 250 Q144 257 192 250 Q240 243 288 250 Q320 254 360 250" stroke="#D42B2B" strokeWidth="1.5" fill="none" opacity="0.28" strokeDasharray="6 4"/>
      <g transform="translate(58,225)">
        <path d="M0 9 Q18 5 36 9 L32 18 L4 18Z" fill="#D42B2B" stroke="#A01E1E" strokeWidth="1.5"/>
        <line x1="18" y1="5" x2="18" y2="-18" stroke="#A01E1E" strokeWidth="2" strokeLinecap="round"/>
        <path d="M18 -16 L34 -4 L18 2Z" fill="#F5DADA" stroke="#D42B2B" strokeWidth="1.5"/>
      </g>
      <g transform="translate(278,178)">
        <line x1="0" y1="58" x2="-4" y2="0" stroke="#A01E1E" strokeWidth="3" strokeLinecap="round"/>
        <path d="M-4 0 Q-28 -13 -38 -9" stroke="#D42B2B" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
        <path d="M-4 0 Q6 -23 20 -20" stroke="#D42B2B" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
        <path d="M-4 0 Q-14 -26 -7 -33" stroke="#D42B2B" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
        <circle cx="-4" cy="-1" r="4.5" fill="#D42B2B" opacity="0.38"/>
      </g>
      <g transform="translate(118,58) rotate(-20)">
        <path d="M0 0 L28 -4 Q34 -4 34 0 Q34 4 28 4 L0 0Z" fill="#D42B2B" opacity="0.55"/>
        <path d="M9 0 L4 -11 L15 -7Z" fill="#D42B2B" opacity="0.45"/>
        <line x1="34" y1="0" x2="48" y2="0" stroke="#D42B2B" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.45"/>
      </g>
      <g fill="#D42B2B" opacity="0.45">
        <path d="M48 58 L50 53 L52 58 L57 60 L52 62 L50 67 L48 62 L43 60Z"/>
        <path d="M308 148 L310 144 L312 148 L316 150 L312 152 L310 156 L308 152 L304 150Z"/>
      </g>
      <g transform="translate(168,93)">
        <path d="M0 0 Q-13 -13 -13 -23 Q-13 -36 0 -36 Q13 -36 13 -23 Q13 -13 0 0Z" fill="#D42B2B" stroke="#A01E1E" strokeWidth="1.5"/>
        <circle cx="0" cy="-23" r="5.5" fill="white"/>
      </g>
      <rect x="10" y="10" width="340" height="310" rx="18" stroke="#D42B2B" strokeWidth="1.5" strokeDasharray="8 5" fill="none" opacity="0.18"/>
      <g transform="translate(318,272)">
        <circle cx="0" cy="0" r="13" stroke="#D42B2B" strokeWidth="1.5" fill="white" opacity="0.8"/>
        <path d="M0 -9 L2.5 -2 L0 2 L-2.5 -2Z" fill="#D42B2B"/>
        <path d="M0 9 L2.5 2 L0 -2 L-2.5 2Z" fill="#D42B2B" opacity="0.28"/>
        <path d="M-9 0 L-2 2.5 L2 0 L-2 -2.5Z" fill="#D42B2B" opacity="0.28"/>
        <path d="M9 0 L2 2.5 L-2 0 L2 -2.5Z" fill="#D42B2B" opacity="0.28"/>
        <circle cx="0" cy="0" r="2.5" fill="white" stroke="#D42B2B" strokeWidth="1"/>
      </g>
    </svg>
  );
}
