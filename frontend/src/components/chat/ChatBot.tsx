import { useState, useRef, useEffect } from 'react';
import { ImageWithFallback } from '../common/ImageWithFallback';

// ─── Types ────────────────────────────────────────────────────────────────────

interface DestCard {
  name: string;
  location: string;
  price: string;
  rating: string;
  image: string;
  badge: string;
}

interface PackageCard {
  destination: string;
  hotel: string;
  nights: number;
  price: string;
  image: string;
  rating: string;
}

interface BotMsg {
  id: string;
  kind: 'bot';
  text: string;
  chips?: string[];
}

interface UserMsg {
  id: string;
  kind: 'user';
  text: string;
}

type ChatMsg = BotMsg | UserMsg;

// Recommendation block pushed to the right-hand showcase panel.
interface RecoBlock {
  id: string;
  title: string;
  destCards?: DestCard[];
  packageCard?: PackageCard;
}

// ─── Data helpers ─────────────────────────────────────────────────────────────

function getDestCards(destType: string): DestCard[] {
  if (destType.includes('Biển')) {
    return [
      { name: 'Phú Quốc', location: 'Kiên Giang', price: 'từ 2.9tr₫', rating: '4.9 ★', image: 'https://images.unsplash.com/photo-1732243395944-cb3ff9311091?w=480&h=300&fit=crop&auto=format', badge: 'Hot ✦' },
      { name: 'Nha Trang', location: 'Khánh Hòa', price: 'từ 1.8tr₫', rating: '4.7 ★', image: 'https://images.unsplash.com/photo-1572572216428-91def7b78278?w=480&h=300&fit=crop&auto=format', badge: 'Bán chạy' },
    ];
  }
  if (destType.includes('Núi')) {
    return [
      { name: 'Sa Pa', location: 'Lào Cai', price: 'từ 1.6tr₫', rating: '4.8 ★', image: 'https://images.unsplash.com/photo-1665905905591-fb66b0496481?w=480&h=300&fit=crop&auto=format', badge: 'Đẹp nhất' },
      { name: 'Đà Lạt', location: 'Lâm Đồng', price: 'từ 1.2tr₫', rating: '4.6 ★', image: 'https://images.unsplash.com/photo-1732098407342-6b6a05e3da3d?w=480&h=300&fit=crop&auto=format', badge: 'Mới ✦' },
    ];
  }
  if (destType.includes('Phố cổ')) {
    return [
      { name: 'Hội An', location: 'Quảng Nam', price: 'từ 1.5tr₫', rating: '4.9 ★', image: 'https://images.unsplash.com/photo-1596401057633-54a8fe8ef647?w=480&h=300&fit=crop&auto=format', badge: 'Di sản ✦' },
      { name: 'Hà Nội Cổ', location: 'Hà Nội', price: 'từ 1.0tr₫', rating: '4.7 ★', image: 'https://images.unsplash.com/photo-1691927644490-e1a24b366a5e?w=480&h=300&fit=crop&auto=format', badge: 'Văn hóa' },
    ];
  }
  return [
    { name: 'VinWonders Phú Quốc', location: 'Kiên Giang', price: 'từ 890k₫', rating: '4.9 ★', image: 'https://images.unsplash.com/photo-1732243395944-cb3ff9311091?w=480&h=300&fit=crop&auto=format', badge: 'Vui nhất VN' },
    { name: 'VinWonders Đà Nẵng', location: 'Đà Nẵng', price: 'từ 750k₫', rating: '4.8 ★', image: 'https://images.unsplash.com/photo-1573270689103-d7a4e42b609a?w=480&h=300&fit=crop&auto=format', badge: 'Nổi bật' },
  ];
}

function getPackageCard(budget: string, destType: string): PackageCard {
  const isBeach = destType.includes('Biển') || destType.includes('Vui chơi');
  const price = budget.includes('Dưới') ? (isBeach ? '2.450.000₫' : '1.850.000₫')
    : budget.includes('2–5') ? (isBeach ? '3.990.000₫' : '3.200.000₫')
    : (isBeach ? '6.900.000₫' : '5.500.000₫');
  if (isBeach) {
    return { destination: 'Phú Quốc', hotel: 'Vinpearl Resort & Spa Phú Quốc', nights: 3, price, image: 'https://images.unsplash.com/photo-1777919541977-16d7271ac96e?w=560&h=240&fit=crop&auto=format', rating: '5.0' };
  }
  if (destType.includes('Núi')) {
    return { destination: 'Sa Pa', hotel: 'Vinpearl Premium Sa Pa', nights: 2, price, image: 'https://images.unsplash.com/photo-1665905905591-fb66b0496481?w=560&h=240&fit=crop&auto=format', rating: '4.9' };
  }
  return { destination: 'Hội An', hotel: 'Vinpearl Premium Hội An', nights: 2, price, image: 'https://images.unsplash.com/photo-1701421016474-09b19faa9f77?w=560&h=240&fit=crop&auto=format', rating: '4.9' };
}

const STEP1_MSG: BotMsg = {
  id: 'step1',
  kind: 'bot',
  text: 'Xin chào! 👋 Mình là VinBot — trợ lý du lịch thông minh của VinJourney. Bạn muốn đi dạng nào?',
  chips: ['🌊 Biển', '⛰️ Núi', '🏛️ Phố cổ', '🎡 Vui chơi'],
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function VinBotAvatar({ size = 44 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
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

function TypingDots() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', animation: 'vinbot-msg-in .3s ease both' }}>
      <VinBotAvatar size={32} />
      <div style={{
        background: 'white', border: '1.5px dashed #D42B2B',
        borderRadius: '4px 14px 14px 14px', padding: '10px 16px',
        display: 'flex', gap: '4px', alignItems: 'center',
      }}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            width: '7px', height: '7px', borderRadius: '50%', background: '#D42B2B',
            display: 'inline-block', opacity: 0.7,
            animation: `vinbot-bounce 1.1s ${i * 0.18}s ease-in-out infinite`,
          }} />
        ))}
      </div>
    </div>
  );
}

// Hotel card shown in the right-hand showcase panel.
function HotelCard({ card }: { card: DestCard }) {
  return (
    <div
      style={{
        border: '2px solid #F5DADA', borderRadius: '18px', overflow: 'hidden',
        background: 'white', cursor: 'pointer', position: 'relative',
        boxShadow: '3px 3px 0 #F5DADA',
        transition: 'transform .2s cubic-bezier(0.34,1.56,0.64,1), box-shadow .2s, border-color .2s',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.transform = 'translateY(-6px)';
        e.currentTarget.style.boxShadow = '6px 8px 0 #F5DADA';
        e.currentTarget.style.borderColor = '#D42B2B';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = '';
        e.currentTarget.style.boxShadow = '3px 3px 0 #F5DADA';
        e.currentTarget.style.borderColor = '#F5DADA';
      }}
    >
      <div style={{ position: 'relative', height: '150px', overflow: 'hidden', background: '#FDE8E0' }}>
        <ImageWithFallback src={card.image} alt={card.name} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
        <span style={{
          position: 'absolute', top: '10px', left: '10px',
          background: '#D42B2B', color: 'white', fontFamily: "'Pangolin', cursive",
          fontSize: '12px', padding: '3px 10px', borderRadius: '99px',
          border: '1.5px solid #A01E1E', transform: 'rotate(-3deg)',
        }}>{card.badge}</span>
      </div>
      <div style={{ padding: '12px 14px' }}>
        <div style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '20px', fontWeight: 700, color: '#2A1A1A' }}>{card.name}</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: '6px' }}>
          <div>
            <div style={{ fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '12px', color: '#5A3A3A' }}>📍 {card.location}</div>
            <div style={{ fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '12px', color: '#D42B2B', marginTop: '2px' }}>{card.rating}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '17px', fontWeight: 700, color: '#D42B2B' }}>{card.price}</div>
            <button
              style={{
                marginTop: '4px',
                background: '#D42B2B', color: 'white',
                border: '1.5px solid #A01E1E', borderRadius: '8px',
                fontFamily: "'Pangolin', cursive", fontSize: '12px',
                padding: '4px 12px', cursor: 'pointer',
                boxShadow: '2px 2px 0 #A01E1E',
                transition: 'transform .1s, box-shadow .1s',
              }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'translate(-1px,-1px)'; e.currentTarget.style.boxShadow = '3px 3px 0 #A01E1E'; }}
              onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = '2px 2px 0 #A01E1E'; }}
            >
              Xem ngay →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PackageCardInline({ card }: { card: PackageCard }) {
  return (
    <div style={{
      border: '2px solid #D42B2B', borderRadius: '16px', overflow: 'hidden',
      background: 'white', boxShadow: '3px 3px 0 #F5DADA',
      transition: 'transform .2s, box-shadow .2s',
    }}
      onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.boxShadow = '5px 7px 0 #F5DADA'; }}
      onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = '3px 3px 0 #F5DADA'; }}
    >
      <div style={{ position: 'relative', height: '180px', background: '#FDE8E0' }}>
        <ImageWithFallback src={card.image} alt={card.destination} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(to top, rgba(42,26,26,0.6) 0%, transparent 60%)',
        }} />
        <div style={{ position: 'absolute', bottom: '10px', left: '14px', color: 'white' }}>
          <div style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '22px', fontWeight: 700 }}>{card.destination}</div>
          <div style={{ fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '12px', opacity: 0.9 }}>{card.hotel}</div>
        </div>
        <div style={{
          position: 'absolute', top: '10px', right: '10px',
          background: '#D42B2B', color: 'white', fontFamily: "'Pangolin', cursive", fontSize: '13px',
          padding: '3px 12px', borderRadius: '99px', border: '1.5px solid #A01E1E',
        }}>
          ⭐ {card.rating}
        </div>
      </div>
      <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
        <div>
          <div style={{ fontFamily: "'Pangolin', cursive", fontSize: '13px', color: '#5A3A3A' }}>
            🏨 {card.hotel}
          </div>
          <div style={{ fontFamily: "'Pangolin', cursive", fontSize: '13px', color: '#5A3A3A', marginTop: '2px' }}>
            🌙 {card.nights} đêm · Combo bay + nghỉ
          </div>
          <div style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '22px', fontWeight: 700, color: '#D42B2B', marginTop: '6px' }}>
            {card.price}
            <span style={{ fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '12px', fontWeight: 400, color: '#5A3A3A' }}> /người</span>
          </div>
        </div>
        <button style={{
          background: '#D42B2B', color: 'white',
          border: '2px solid #A01E1E', borderRadius: '12px',
          fontFamily: "'Pangolin', cursive", fontSize: '16px',
          padding: '10px 20px', cursor: 'pointer', flexShrink: 0,
          boxShadow: '3px 3px 0 #A01E1E',
          transition: 'transform .1s, box-shadow .1s',
        }}
          onMouseEnter={e => { e.currentTarget.style.transform = 'translate(-1px,-1px)'; e.currentTarget.style.boxShadow = '4px 4px 0 #A01E1E'; }}
          onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = '3px 3px 0 #A01E1E'; }}
        >
          Đặt ngay ✈
        </button>
      </div>
    </div>
  );
}

function QuickReplyChips({ chips, onChip, disabled }: { chips: string[]; onChip: (c: string) => void; disabled: boolean }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
      {chips.map(chip => (
        <button
          key={chip}
          onClick={() => !disabled && onChip(chip)}
          disabled={disabled}
          style={{
            fontFamily: "'Pangolin', cursive", fontSize: '13px',
            color: disabled ? '#A0A0A0' : '#D42B2B',
            border: `1.5px dashed ${disabled ? '#D0D0D0' : '#D42B2B'}`,
            borderRadius: '99px', padding: '4px 14px',
            background: disabled ? '#F5F5F5' : 'white',
            cursor: disabled ? 'default' : 'pointer',
            transition: 'background .15s, transform .12s cubic-bezier(0.34,1.56,0.64,1)',
          }}
          onMouseEnter={e => { if (!disabled) { e.currentTarget.style.background = '#FDF3F3'; e.currentTarget.style.transform = 'translateY(-2px) scale(1.04)'; } }}
          onMouseLeave={e => { if (!disabled) { e.currentTarget.style.background = 'white'; e.currentTarget.style.transform = ''; } }}
        >
          {chip}
        </button>
      ))}
    </div>
  );
}

function BotBubble({
  msg, onChip, chipsDisabled,
}: { msg: BotMsg; onChip: (c: string) => void; chipsDisabled: boolean }) {
  return (
    <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', marginBottom: '14px', animation: 'vinbot-msg-in .35s ease both' }}>
      <div style={{ flexShrink: 0, marginTop: '2px' }}>
        <VinBotAvatar size={32} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          background: 'white', border: '1.5px dashed #D42B2B',
          borderRadius: '4px 14px 14px 14px', padding: '10px 14px',
          fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '14px',
          color: '#2A1A1A', lineHeight: 1.6,
          boxShadow: '2px 2px 0 #F5DADA',
        }}>
          {msg.text}
        </div>
        {msg.chips && (
          <QuickReplyChips chips={msg.chips} onChip={onChip} disabled={chipsDisabled} />
        )}
      </div>
    </div>
  );
}

function UserBubble({ msg }: { msg: UserMsg }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '14px', animation: 'vinbot-msg-in .35s ease both' }}>
      <div style={{
        background: '#D42B2B', color: 'white',
        borderRadius: '14px 4px 14px 14px', padding: '10px 14px',
        fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '14px',
        lineHeight: 1.6, maxWidth: '75%',
        boxShadow: '2px 2px 0 #A01E1E',
      }}>
        {msg.text}
      </div>
    </div>
  );
}

// One recommendation block rendered in the right showcase panel.
function RecoBlockView({ block }: { block: RecoBlock }) {
  return (
    <div style={{ marginBottom: '22px', animation: 'vinbot-pop .4s cubic-bezier(0.34,1.56,0.64,1) both' }}>
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: '6px',
        fontFamily: "'Pangolin', cursive", fontSize: '14px', color: '#D42B2B',
        background: '#FDF3F3', border: '1.5px dashed #D42B2B',
        borderRadius: '99px', padding: '4px 14px', marginBottom: '14px',
        transform: 'rotate(-1deg)',
      }}>
        ✦ {block.title}
      </div>
      {block.destCards && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))', gap: '16px' }}>
          {block.destCards.map((card, i) => (
            <div key={i} style={{ animation: `vinbot-card-in .45s ${i * 0.1}s ease both` }}>
              <HotelCard card={card} />
            </div>
          ))}
        </div>
      )}
      {block.packageCard && (
        <div style={{ animation: 'vinbot-card-in .45s ease both' }}>
          <PackageCardInline card={block.packageCard} />
        </div>
      )}
    </div>
  );
}

// ─── Main ChatBot component ───────────────────────────────────────────────────

interface ChatBotProps {
  isOpen: boolean;
  onOpen: () => void;
  onClose: () => void;
}

export function ChatBot({ isOpen, onOpen, onClose }: ChatBotProps) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [step, setStep] = useState(0);
  const [destType, setDestType] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [disabledChipMsgIds, setDisabledChipMsgIds] = useState<Set<string>>(new Set());
  const [recoBlocks, setRecoBlocks] = useState<RecoBlock[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const recoScrollRef = useRef<HTMLDivElement>(null);
  const hasOpened = useRef(false);

  useEffect(() => {
    if (isOpen && !hasOpened.current) {
      hasOpened.current = true;
      setIsTyping(true);
      setTimeout(() => {
        setIsTyping(false);
        setMessages([STEP1_MSG]);
        setStep(1);
      }, 900);
    }
  }, [isOpen]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, isTyping]);

  // Reveal newest recommendation in the showcase panel.
  useEffect(() => {
    const el = recoScrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [recoBlocks]);

  // Lock background scroll + close on Escape while the split view is open.
  useEffect(() => {
    if (!isOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener('keydown', onKey);
    };
  }, [isOpen, onClose]);

  const addUserMsg = (text: string) => {
    const msg: UserMsg = { id: Date.now().toString(), kind: 'user', text };
    setMessages(prev => [...prev, msg]);
    return msg;
  };

  const addBotMsg = (partial: Omit<BotMsg, 'id'>) => {
    const msg: BotMsg = { id: Date.now().toString() + '-bot', ...partial };
    setMessages(prev => [...prev, msg]);
  };

  const addReco = (partial: Omit<RecoBlock, 'id'>) => {
    setRecoBlocks(prev => [...prev, { id: Date.now().toString() + '-reco', ...partial }]);
  };

  const disableLastChips = (msgId: string) => {
    setDisabledChipMsgIds(prev => new Set([...prev, msgId]));
  };

  const handleChip = (chip: string, fromMsgId: string) => {
    disableLastChips(fromMsgId);
    addUserMsg(chip);
    setIsTyping(true);

    if (step === 1) {
      const dt = chip;
      setDestType(dt);
      setTimeout(() => {
        setIsTyping(false);
        addBotMsg({
          kind: 'bot',
          text: `Tuyệt! ${dt} — mình vừa hiển thị 2 điểm đến cực hot ở bảng bên phải nhé →`,
          chips: ['💰 Dưới 2 triệu', '💳 2–5 triệu', '💎 Trên 5 triệu'],
        });
        addReco({ title: `Điểm đến gợi ý · ${dt}`, destCards: getDestCards(dt) });
        setStep(2);
      }, 1300);
    } else if (step === 2) {
      setTimeout(() => {
        setIsTyping(false);
        addBotMsg({
          kind: 'bot',
          text: `Hoàn hảo! Với ngân sách ${chip.replace(/[💰💳💎]\s*/g, '')}, gói du lịch dành riêng cho bạn đã xuất hiện bên phải ✦`,
        });
        addReco({ title: 'Gói du lịch dành riêng cho bạn', packageCard: getPackageCard(chip, destType) });
        setStep(3);
        setTimeout(() => {
          addBotMsg({
            kind: 'bot',
            text: 'Bạn có muốn tìm thêm lựa chọn khác không?',
            chips: ['🔄 Bắt đầu lại', '📞 Liên hệ tư vấn viên'],
          });
        }, 600);
      }, 1400);
    } else if (chip.includes('Bắt đầu lại')) {
      handleReset();
    }
  };

  const handleSend = () => {
    if (!input.trim()) return;
    const txt = input;
    setInput('');
    addUserMsg(txt);
    setIsTyping(true);
    setTimeout(() => {
      setIsTyping(false);
      addBotMsg({
        kind: 'bot',
        text: 'Mình đang tìm kiếm gợi ý phù hợp cho bạn! Hãy thử chọn loại hình du lịch để mình tư vấn chính xác hơn nhé 🔍',
        chips: ['🌊 Biển', '⛰️ Núi', '🏛️ Phố cổ', '🎡 Vui chơi'],
      });
      setStep(1);
    }, 1000);
  };

  const handleReset = () => {
    setMessages([]);
    setStep(0);
    setDestType('');
    setDisabledChipMsgIds(new Set());
    setRecoBlocks([]);
    hasOpened.current = false;
    setIsTyping(true);
    setTimeout(() => {
      hasOpened.current = true;
      setIsTyping(false);
      setMessages([STEP1_MSG]);
      setStep(1);
    }, 900);
  };

  const totalHotels = recoBlocks.reduce((n, b) => n + (b.destCards?.length ?? 0) + (b.packageCard ? 1 : 0), 0);

  return (
    <>
      <style>{`
        @keyframes vinbot-bounce {
          0%, 100% { transform: translateY(0); opacity: 0.5; }
          50% { transform: translateY(-5px); opacity: 1; }
        }
        @keyframes vinbot-msg-in {
          from { opacity: 0; transform: translateY(10px) scale(0.97); }
          to   { opacity: 1; transform: none; }
        }
        @keyframes vinbot-card-in {
          from { opacity: 0; transform: translateX(26px) rotate(1.5deg); }
          to   { opacity: 1; transform: none; }
        }
        @keyframes vinbot-pop {
          0%   { opacity: 0; transform: scale(0.9); }
          60%  { transform: scale(1.02); }
          100% { opacity: 1; transform: scale(1); }
        }
        @keyframes vinbot-float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-10px); }
        }
        @keyframes vinbot-backdrop {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes vinbot-panel-left {
          from { opacity: 0; transform: translateX(-44px) scale(0.98); }
          to   { opacity: 1; transform: none; }
        }
        @keyframes vinbot-panel-right {
          from { opacity: 0; transform: translateX(44px) scale(0.98); }
          to   { opacity: 1; transform: none; }
        }
        @keyframes vinbot-pulse-ring {
          0%   { transform: scale(1); opacity: 0.55; }
          100% { transform: scale(1.9); opacity: 0; }
        }
      `}</style>

      {/* Floating button */}
      <button
        onClick={onOpen}
        title="Hỏi VinBot"
        style={{
          position: 'fixed', bottom: '28px', right: '28px',
          width: '62px', height: '62px',
          background: '#D42B2B', border: '2.5px solid #A01E1E',
          borderRadius: '18px', cursor: 'pointer',
          boxShadow: '4px 4px 0 #A01E1E',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 999,
          transform: isOpen ? 'scale(0)' : 'scale(1) rotate(-2deg)',
          transition: 'transform 0.25s cubic-bezier(0.34,1.56,0.64,1)',
        }}
      >
        {!isOpen && (
          <span style={{
            position: 'absolute', inset: 0, borderRadius: '18px',
            border: '2.5px solid #D42B2B',
            animation: 'vinbot-pulse-ring 1.8s ease-out infinite',
          }} />
        )}
        <svg width="30" height="30" viewBox="0 0 30 30" fill="none">
          <rect x="3" y="3" width="24" height="18" rx="5" fill="white" opacity="0.95"/>
          <circle cx="10" cy="12" r="2" fill="#D42B2B"/>
          <circle cx="15" cy="12" r="2" fill="#D42B2B"/>
          <circle cx="20" cy="12" r="2" fill="#D42B2B"/>
          <path d="M10 21 L10 27 L16 21Z" fill="white" opacity="0.95"/>
        </svg>
      </button>

      {/* Split-screen overlay */}
      {isOpen && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(42,26,26,0.4)', backdropFilter: 'blur(3px)',
            display: 'flex', gap: '20px', padding: '22px',
            animation: 'vinbot-backdrop 0.3s ease both',
          }}
        >
          {/* ── Left: chat ── */}
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: '44%', minWidth: '360px', height: '100%',
              background: '#FFFDF8',
              border: '2.5px solid #D42B2B',
              borderRadius: '20px',
              boxShadow: '4px 4px 0 #F5DADA',
              display: 'flex', flexDirection: 'column',
              overflow: 'hidden',
              animation: 'vinbot-panel-left 0.4s cubic-bezier(0.34,1.56,0.64,1) both',
            }}
          >
            {/* Header */}
            <div style={{
              background: '#D42B2B',
              padding: '14px 16px',
              display: 'flex', alignItems: 'center', gap: '12px',
              borderBottom: '2px solid #A01E1E',
              flexShrink: 0,
            }}>
              <div style={{ position: 'relative' }}>
                <VinBotAvatar size={44} />
                <span style={{
                  position: 'absolute', bottom: '1px', right: '1px',
                  width: '10px', height: '10px', background: '#4ADE80',
                  borderRadius: '50%', border: '2px solid white',
                }} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '18px', fontWeight: 700, color: 'white' }}>
                  VinBot ✦
                </div>
                <div style={{ fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '12px', color: 'rgba(255,255,255,0.82)' }}>
                  Trợ lý du lịch của bạn • Phản hồi ngay
                </div>
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  onClick={handleReset}
                  title="Cuộc hội thoại mới"
                  style={{ background: 'rgba(255,255,255,0.18)', border: 'none', borderRadius: '8px', width: '32px', height: '32px', cursor: 'pointer', color: 'white', fontSize: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'background .15s' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.32)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.18)')}
                >
                  ↺
                </button>
                <button
                  onClick={onClose}
                  title="Đóng"
                  style={{ background: 'rgba(255,255,255,0.18)', border: 'none', borderRadius: '8px', width: '32px', height: '32px', cursor: 'pointer', color: 'white', fontSize: '18px', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'background .15s' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.32)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.18)')}
                >
                  ×
                </button>
              </div>
            </div>

            {/* Journey progress bar */}
            <div style={{ background: '#FFF5EC', padding: '8px 16px', borderBottom: '1px solid #F5DADA', display: 'flex', gap: '8px', alignItems: 'center', flexShrink: 0 }}>
              {['Loại hình', 'Điểm đến', 'Gói du lịch'].map((label, i) => {
                const active = step > i;
                const current = step === i + 1;
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1 }}>
                    <div style={{
                      width: '22px', height: '22px', borderRadius: '50%', flexShrink: 0,
                      background: active ? '#D42B2B' : current ? '#FDF3F3' : 'white',
                      border: `2px ${active ? 'solid' : 'dashed'} #D42B2B`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontFamily: "'Pangolin', cursive", fontSize: '11px',
                      color: active ? 'white' : '#D42B2B',
                      transform: current ? 'scale(1.15)' : 'scale(1)',
                      transition: 'all .3s cubic-bezier(0.34,1.56,0.64,1)',
                    }}>
                      {active ? '✓' : i + 1}
                    </div>
                    <span style={{ fontFamily: "'Pangolin', cursive", fontSize: '11px', color: active || current ? '#D42B2B' : '#A0A0A0', whiteSpace: 'nowrap' }}>
                      {label}
                    </span>
                    {i < 2 && <div style={{ flex: 1, height: '1.5px', background: active ? '#D42B2B' : '#F5DADA', transition: 'background .3s' }} />}
                  </div>
                );
              })}
            </div>

            {/* Messages */}
            <div
              ref={scrollRef}
              style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '0' }}
            >
              {messages.map(msg =>
                msg.kind === 'user'
                  ? <UserBubble key={msg.id} msg={msg} />
                  : <BotBubble
                      key={msg.id}
                      msg={msg}
                      onChip={(chip) => handleChip(chip, msg.id)}
                      chipsDisabled={disabledChipMsgIds.has(msg.id)}
                    />
              )}
              {isTyping && <TypingDots />}
              <div style={{ height: '4px' }} />
            </div>

            {/* Input bar */}
            <div style={{
              padding: '10px 12px',
              borderTop: '2px dashed #F5DADA',
              background: 'white',
              display: 'flex', gap: '8px', alignItems: 'center',
              flexShrink: 0,
            }}>
              <input
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSend()}
                placeholder="Nhập tin nhắn hoặc chọn gợi ý bên trên..."
                style={{
                  flex: 1, padding: '10px 14px',
                  border: '2px solid #F5DADA', borderRadius: '12px',
                  fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '14px',
                  color: '#2A1A1A', background: '#FFFDF8', outline: 'none',
                  transition: 'border-color .2s',
                }}
                onFocus={e => (e.target.style.borderColor = '#D42B2B')}
                onBlur={e => (e.target.style.borderColor = '#F5DADA')}
              />
              <button
                title="Giọng nói"
                style={{ width: '38px', height: '38px', borderRadius: '10px', border: '1.5px dashed #D42B2B', background: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'background .15s' }}
                onMouseEnter={e => (e.currentTarget.style.background = '#FDF3F3')}
                onMouseLeave={e => (e.currentTarget.style.background = 'white')}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <rect x="9" y="2" width="6" height="11" rx="3" fill="#D42B2B" opacity="0.7"/>
                  <path d="M5 10Q5 17 12 17Q19 17 19 10" stroke="#D42B2B" strokeWidth="2" fill="none" strokeLinecap="round"/>
                  <line x1="12" y1="17" x2="12" y2="21" stroke="#D42B2B" strokeWidth="2" strokeLinecap="round"/>
                  <line x1="9" y1="21" x2="15" y2="21" stroke="#D42B2B" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
              <button
                onClick={handleSend}
                style={{
                  width: '38px', height: '38px', borderRadius: '10px',
                  background: '#D42B2B', border: '2px solid #A01E1E',
                  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: '2px 2px 0 #A01E1E', flexShrink: 0,
                  transition: 'transform .1s, box-shadow .1s',
                }}
                onMouseEnter={e => { e.currentTarget.style.transform = 'translate(-1px,-1px)'; e.currentTarget.style.boxShadow = '3px 3px 0 #A01E1E'; }}
                onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = '2px 2px 0 #A01E1E'; }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M22 2L11 13" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
                  <path d="M22 2L15 22L11 13L2 9L22 2Z" fill="white" opacity="0.9"/>
                </svg>
              </button>
            </div>
          </div>

          {/* ── Right: hotel showcase ── */}
          <div
            onClick={e => e.stopPropagation()}
            style={{
              flex: 1, height: '100%',
              background: '#FFFDF8',
              border: '2.5px solid #D42B2B',
              borderRadius: '20px',
              boxShadow: '4px 4px 0 #F5DADA',
              display: 'flex', flexDirection: 'column',
              overflow: 'hidden',
              animation: 'vinbot-panel-right 0.4s cubic-bezier(0.34,1.56,0.64,1) both',
            }}
          >
            {/* Panel header */}
            <div style={{
              padding: '16px 20px', flexShrink: 0,
              borderBottom: '2px dashed #F5DADA',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              background: 'white',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '22px' }}>🏨</span>
                <div>
                  <div style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '20px', fontWeight: 700, color: '#2A1A1A' }}>
                    Khách sạn <span style={{ color: '#D42B2B' }}>gợi ý</span> cho bạn
                  </div>
                  <div style={{ fontFamily: "'Pangolin', cursive", fontSize: '12px', color: '#5A3A3A' }}>
                    VinBot chọn lọc theo cuộc trò chuyện của bạn ✦
                  </div>
                </div>
              </div>
              {totalHotels > 0 && (
                <span style={{
                  fontFamily: "'Pangolin', cursive", fontSize: '13px', color: 'white',
                  background: '#D42B2B', border: '1.5px solid #A01E1E',
                  borderRadius: '99px', padding: '4px 12px', transform: 'rotate(-2deg)',
                }}>
                  {totalHotels} lựa chọn
                </span>
              )}
            </div>

            {/* Panel body */}
            <div ref={recoScrollRef} style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
              {recoBlocks.length === 0 ? (
                <div style={{
                  height: '100%', display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center', gap: '16px', textAlign: 'center',
                }}>
                  <div style={{ animation: 'vinbot-float 3s ease-in-out infinite' }}>
                    <VinBotAvatar size={84} />
                  </div>
                  <div style={{
                    fontFamily: "'Baloo 2', sans-serif", fontSize: '20px', fontWeight: 700, color: '#2A1A1A',
                  }}>
                    Chưa có gợi ý nào
                  </div>
                  <div style={{
                    fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: '14px', color: '#5A3A3A',
                    maxWidth: '320px', lineHeight: 1.6,
                  }}>
                    Hãy trò chuyện với VinBot bên trái — những khách sạn được gợi ý sẽ lần lượt xuất hiện ở đây 🌟
                  </div>
                </div>
              ) : (
                recoBlocks.map(block => <RecoBlockView key={block.id} block={block} />)
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
