import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { t } from '../../styles/theme';
import { sendChatMessageStream, notifySessionEnd, logReaction, logFinalReaction, type BackendChatData } from '../../services/backendApi';
import { type Hotel, type HotelListParams, type RecoQuery, extractImages } from '../../services/hotels';
import { useAuth } from '../../hooks/useAuth';

// Bề rộng chat dock bên phải — trang chừa đúng khoảng này để không bị che.
export const CHAT_DOCK_WIDTH = 440;

// ─── Types ────────────────────────────────────────────────────────────────────

interface BotMsg {
  id: string;
  kind: 'bot';
  text: string;
  chips?: string[];
  suggestionActions?: boolean;
  /** true khi bubble đang hiển thị status pipeline, false/undefined khi là answer thật */
  isStatus?: boolean;
}

interface UserMsg {
  id: string;
  kind: 'user';
  text: string;
}

// STEP1_MSG id — dùng để loại trừ nút reaction trên tin chào mừng đầu tiên
const WELCOME_MSG_ID = 'step1';

type ChatMsg = BotMsg | UserMsg;

// ─── Map hội thoại → bộ lọc API thật ──────────────────────────────────────────
// Loại hình → thành phố tiêu biểu (đã kiểm tra đều có khách sạn trong API).

function cityForDest(dt: string): string | undefined {
  if (dt.includes('Biển')) return 'Phú Quốc';
  if (dt.includes('Núi')) return 'Đà Lạt';
  if (dt.includes('Phố cổ')) return 'Hội An';
  if (dt.includes('Vui chơi')) return 'Đà Nẵng';
  return undefined;
}

function budgetToPrice(budget: string): Pick<HotelListParams, 'price_min' | 'price_max'> {
  if (budget.includes('Dưới')) return { price_max: 2_000_000 };
  if (budget.includes('2')) return { price_min: 2_000_000, price_max: 5_000_000 };
  return { price_min: 5_000_000 };
}

const STEP1_MSG: BotMsg = {
  id: 'step1',
  kind: 'bot',
  text: 'Xin chào! Mình là VinBot — trợ lý du lịch thông minh từ VinJourney. Bạn đang tìm kiếm một kỳ nghỉ dưỡng thư giãn, một chuyến phiêu lưu khám phá, hay cần mình lên một lịch trình cụ thể?',
};

function createSessionId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatBackendReply(data: BackendChatData): string {
  const answer = data.clarification_question || data.answer || data.explanation;
  if (answer) return answer;

  const recommendations = data.recommendations ?? [];
  if (recommendations.length > 0) {
    const names = recommendations
      .slice(0, 3)
      .map((item) => String(item.hotel_name ?? item.name ?? item.hotel_id ?? 'khách sạn phù hợp'))
      .join(', ');
    return `Mình tìm thấy ${recommendations.length} gợi ý phù hợp. Một vài lựa chọn nổi bật: ${names}.`;
  }

  return 'Mình chưa tìm thấy câu trả lời phù hợp. Bạn có thể nói rõ hơn về điểm đến, ngày đi hoặc ngân sách không?';
}

function suggestionChips(data: BackendChatData): string[] | undefined {
  const suggestions = (data.next_suggestions ?? [])
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 3);
  return suggestions.length ? suggestions : undefined;
}

function toNumber(value: unknown): number | undefined {
  if (value === null || value === undefined || value === '') return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function firstString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return undefined;
}

function backendRecommendationToHotel(item: Record<string, unknown>): Hotel | null {
  const metadata = (item.metadata && typeof item.metadata === 'object' ? item.metadata : {}) as Record<string, unknown>;
  const id = toNumber(item.hotel_id ?? item.item_id ?? item.id);
  if (id == null) return null;

  return {
    id,
    name: firstString(item.hotel_name, item.name, metadata.hotel_name, metadata.name) ?? `Khách sạn #${id}`,
    property_type: firstString(item.property_type, metadata.property_type),
    accommodation_type: firstString(item.accommodation_type, item.hotel_type, metadata.accommodation_type, metadata.hotel_type),
    star_rating: toNumber(item.star_rating ?? metadata.star_rating),
    is_luxury: Boolean(item.is_luxury ?? metadata.is_luxury),
    review_score: toNumber(item.review_score ?? metadata.review_score),
    review_count: toNumber(item.review_count ?? metadata.review_count),
    address: firstString(item.address, metadata.address),
    city: firstString(item.city, item.destination, metadata.city, metadata.destination),
    area: firstString(item.area, metadata.area),
    country: firstString(item.country, metadata.country) ?? 'Việt Nam',
    description: firstString(item.description, item.ai_reason, metadata.description),
    min_price: toNumber(item.min_price ?? item.price_min ?? metadata.price_min ?? metadata.min_price),
    images: extractImages({ ...metadata, ...item }),
    amenities: [],
  };
}

function hotelsFromBackend(data: BackendChatData): Hotel[] {
  return (data.recommendations ?? [])
    .map((item) => backendRecommendationToHotel(item))
    .filter((item): item is Hotel => item !== null);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function BotAvatar({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-label="VinFuture">
      <defs>
        <linearGradient id="vin-soft-bg" x1="10" y1="7" x2="38" y2="41" gradientUnits="userSpaceOnUse">
          <stop stopColor="#FFFFFF" />
          <stop offset="1" stopColor="#F4F0E8" />
        </linearGradient>
        <linearGradient id="vin-soft-mark" x1="14" y1="14" x2="34" y2="34" gradientUnits="userSpaceOnUse">
          <stop stopColor={t.navy} />
          <stop offset="1" stopColor={t.ink} />
        </linearGradient>
      </defs>
      <circle cx="24" cy="24" r="23" fill={t.surface} />
      <circle cx="24" cy="24" r="22" stroke={t.borderStrong} />
      <circle cx="24" cy="24" r="18.5" fill="url(#vin-soft-bg)" stroke={t.border} />
      <path
        d="M15.2 15.2C18 15.2 19.8 16.7 20.9 19.7L24 28.2L27.1 19.7C28.2 16.7 30 15.2 32.8 15.2L26.4 33C25.6 35.2 22.4 35.2 21.6 33L15.2 15.2Z"
        fill="url(#vin-soft-mark)"
      />
      <path d="M18.4 35.8C21.9 37.1 26.3 37.1 29.6 35.8" stroke={t.ink3} strokeWidth="1.4" strokeLinecap="round" opacity="0.65" />
    </svg>
  );
}

function TypingDots() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', animation: 'vinbot-msg-in .3s ease both' }}>
      <BotAvatar size={32} />
      <div style={{
        background: t.surface, border: `1px solid ${t.border}`,
        borderRadius: '4px 14px 14px 14px', padding: '12px 16px',
        display: 'flex', gap: '4px', alignItems: 'center', boxShadow: t.shadowSoft,
      }}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            width: '7px', height: '7px', borderRadius: '50%', background: t.ink3,
            display: 'inline-block',
            animation: `vinbot-bounce 1.1s ${i * 0.18}s ease-in-out infinite`,
          }} />
        ))}
      </div>
    </div>
  );
}

function QuickReplyChips({
  chips,
  onChip,
  disabled,
  actions = false,
}: {
  chips: string[];
  onChip: (c: string) => void;
  disabled: boolean;
  actions?: boolean;
}) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: actions ? 'column' : 'row',
      flexWrap: actions ? 'nowrap' : 'wrap',
      gap: '8px',
      marginTop: '10px',
      width: '100%',
    }}>
      {chips.map(chip => (
        <button
          key={chip}
          onClick={() => !disabled && onChip(chip)}
          disabled={disabled}
          aria-label={`Gửi truy vấn: ${chip}`}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: actions ? '10px' : 0,
            width: actions ? '100%' : 'auto',
            textAlign: actions ? 'left' : 'center',
            fontFamily: t.font,
            fontSize: actions ? '14px' : '13px',
            lineHeight: 1.45,
            fontWeight: 500,
            color: disabled ? t.ink3 : (actions ? t.accent : t.ink),
            border: `1px solid ${disabled ? t.border : t.borderStrong}`,
            borderRadius: actions ? '6px' : t.rPill,
            padding: actions ? '10px 12px' : '6px 14px',
            background: disabled ? t.bgSoft : (actions ? t.accentSoft : t.surface),
            cursor: disabled ? 'default' : 'pointer',
            transition: 'background .15s, border-color .15s',
          }}
          onMouseEnter={e => { if (!disabled) { e.currentTarget.style.background = t.accentSoft; e.currentTarget.style.borderColor = t.accent; } }}
          onMouseLeave={e => {
            if (!disabled) {
              e.currentTarget.style.background = actions ? t.accentSoft : t.surface;
              e.currentTarget.style.borderColor = t.borderStrong;
            }
          }}
        >
          {actions && (
            <span aria-hidden="true" style={{ flexShrink: 0, fontSize: '17px', lineHeight: 1 }}>
              ↳
            </span>
          )}
          <span style={{ minWidth: 0, overflowWrap: 'anywhere' }}>{chip}</span>
        </button>
      ))}
    </div>
  );
}

// ── Status stage helpers ──────────────────────────────────────────────────────

function getStatusIcon(message: string): string {
  if (message.includes('phân tích')) return '🔍';
  if (message.includes('tổng hợp')) return '✨';
  return '⏳';
}

function StatusBubble({ msg }: { msg: BotMsg }) {
  const icon = getStatusIcon(msg.text);
  return (
    <div style={{
      display: 'flex', gap: '8px', alignItems: 'flex-start',
      marginBottom: '14px', animation: 'vinbot-msg-in .35s ease both',
    }}>
      {/* Avatar với pulse ring */}
      <div style={{ flexShrink: 0, marginTop: '2px', position: 'relative' }}>
        <BotAvatar size={32} />
        <span style={{
          position: 'absolute', inset: '-3px', borderRadius: '50%',
          border: `2px solid ${t.accent}`,
          animation: 'vinbot-pulse-ring 1.8s ease-out infinite',
        }} />
      </div>

      {/* Bubble status */}
      <div style={{
        background: t.accentSoft,
        border: `1px solid rgba(14,110,99,0.28)`,
        borderRadius: '4px 14px 14px 14px',
        padding: '10px 16px',
        fontFamily: t.font, fontSize: '13px',
        color: t.ink2, lineHeight: 1.5,
        display: 'flex', alignItems: 'center', gap: '8px',
        boxShadow: t.shadowSoft,
        maxWidth: '90%',
      }}>
        <span style={{ fontSize: '16px', flexShrink: 0 }}>{icon}</span>
        <span style={{ fontStyle: 'italic' }}>{msg.text}</span>
        {/* Animated dots inline */}
        <div style={{ display: 'flex', gap: '3px', alignItems: 'center', marginLeft: '4px', flexShrink: 0 }}>
          {[0, 1, 2].map(i => (
            <span key={i} style={{
              width: '4px', height: '4px', borderRadius: '50%',
              background: t.accent, display: 'inline-block', opacity: 0.7,
              animation: `vinbot-bounce 1.1s ${i * 0.18}s ease-in-out infinite`,
            }} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Like/Dislike reaction buttons ────────────────────────────────────────────
function ReactionButtons({
  msgId,
  onReact,
  reacted,
}: {
  msgId: string;
  onReact: (msgId: string, value: boolean) => void;
  reacted: boolean | null; // null = chưa bấm, true = like, false = dislike
}) {
  const liked = reacted === true;
  const disliked = reacted === false;
  const voted = reacted !== null;

  return (
    <div style={{
      display: 'flex', gap: '6px', marginTop: '8px', alignItems: 'center',
    }}>
      <button
        onClick={() => !voted && onReact(msgId, true)}
        disabled={voted}
        aria-label="Thích"
        title="Thích"
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          width: '28px', height: '28px', borderRadius: '50%',
          border: `1px solid ${liked ? t.accent : t.border}`,
          background: liked ? t.accentSoft : 'transparent',
          cursor: voted ? 'default' : 'pointer',
          fontSize: '14px', lineHeight: 1,
          transition: 'all .15s',
          opacity: voted && !liked ? 0.4 : 1,
        }}
      >👍</button>
      <button
        onClick={() => !voted && onReact(msgId, false)}
        disabled={voted}
        aria-label="Không thích"
        title="Không thích"
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          width: '28px', height: '28px', borderRadius: '50%',
          border: `1px solid ${disliked ? '#e74c3c' : t.border}`,
          background: disliked ? 'rgba(231,76,60,0.10)' : 'transparent',
          cursor: voted ? 'default' : 'pointer',
          fontSize: '14px', lineHeight: 1,
          transition: 'all .15s',
          opacity: voted && !disliked ? 0.4 : 1,
        }}
      >👎</button>
    </div>
  );
}

// ─── Satisfaction popup ────────────────────────────────────────────────────────
function SatisfactionPopup({
  onReact,
  onClose,
}: {
  onReact: (value: boolean) => void;
  onClose: () => void;
}) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 2000,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(21,32,51,.45)',
      backdropFilter: 'blur(3px)',
      animation: 'vinbot-backdrop .2s ease both',
    }}>
      <div style={{
        background: t.surface,
        borderRadius: '18px',
        border: `1px solid ${t.border}`,
        boxShadow: t.shadowLg,
        padding: '28px 32px',
        minWidth: '300px',
        maxWidth: '380px',
        position: 'relative',
        fontFamily: t.font,
        animation: 'vinbot-pop .25s cubic-bezier(.34,1.56,.64,1) both',
        textAlign: 'center',
      }}>
        {/* Nút đóng */}
        <button
          onClick={onClose}
          aria-label="Đóng"
          style={{
            position: 'absolute', top: '12px', right: '14px',
            background: 'none', border: 'none',
            fontSize: '18px', cursor: 'pointer',
            color: t.ink3, lineHeight: 1,
          }}
        >✕</button>

        <div style={{ fontSize: '32px', marginBottom: '12px' }}>💬</div>
        <div style={{
          fontSize: '16px', fontWeight: 700,
          color: t.ink, marginBottom: '20px', lineHeight: 1.4,
        }}>
          Bạn có hài lòng với cuộc trò chuyện không?
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', gap: '16px' }}>
          <button
            onClick={() => onReact(true)}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 24px', borderRadius: t.rPill,
              border: `1px solid ${t.accent}`,
              background: t.accentSoft, color: t.accentDark,
              fontFamily: t.font, fontSize: '15px', fontWeight: 600,
              cursor: 'pointer', transition: 'all .15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = t.accent, e.currentTarget.style.color = '#fff')}
            onMouseLeave={e => (e.currentTarget.style.background = t.accentSoft, e.currentTarget.style.color = t.accentDark)}
          >👍 Hài lòng</button>
          <button
            onClick={() => onReact(false)}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 24px', borderRadius: t.rPill,
              border: `1px solid ${t.border}`,
              background: t.bgSoft, color: t.ink2,
              fontFamily: t.font, fontSize: '15px', fontWeight: 600,
              cursor: 'pointer', transition: 'all .15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = '#e74c3c', e.currentTarget.style.color = '#e74c3c')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = t.border, e.currentTarget.style.color = t.ink2)}
          >👎 Chưa hài lòng</button>
        </div>
      </div>
    </div>
  );
}

function BotBubble({
  msg, onChip, chipsDisabled, onReact, reacted, isWelcome,
}: {
  msg: BotMsg;
  onChip: (c: string) => void;
  chipsDisabled: boolean;
  onReact: (msgId: string, value: boolean) => void;
  reacted: boolean | null;
  isWelcome: boolean;
}) {
  if (msg.isStatus) return <StatusBubble msg={msg} />;
  return (
    <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', marginBottom: '14px', animation: 'vinbot-msg-in .35s ease both' }}>
      <div style={{ flexShrink: 0, marginTop: '2px' }}>
        <BotAvatar size={32} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          background: t.surface, border: `1px solid ${t.border}`,
          borderRadius: '4px 14px 14px 14px', padding: '11px 14px',
          fontFamily: t.font, fontSize: '14px',
          color: t.ink, lineHeight: 1.6, boxShadow: t.shadowSoft,
        }}>
          <ReactMarkdown
            components={{
              p: ({ children }) => <p style={{ margin: '0 0 8px' }}>{children}</p>,
              ul: ({ children }) => <ul style={{ margin: '6px 0 8px', paddingLeft: '20px' }}>{children}</ul>,
              ol: ({ children }) => <ol style={{ margin: '6px 0 8px', paddingLeft: '20px' }}>{children}</ol>,
              li: ({ children }) => <li style={{ marginBottom: '4px' }}>{children}</li>,
              h2: ({ children }) => <h2 style={{ margin: '0 0 8px', fontSize: '15px', lineHeight: 1.4 }}>{children}</h2>,
              strong: ({ children }) => <strong style={{ fontWeight: 700 }}>{children}</strong>,
            }}
          >
            {msg.text}
          </ReactMarkdown>
        </div>
        {/* Nút like/dislike — chỉ hiện với tin thật (không phải status, không phải welcome) */}
        {!isWelcome && (
          <ReactionButtons
            msgId={msg.id}
            onReact={onReact}
            reacted={reacted}
          />
        )}
        {msg.chips && (
          <QuickReplyChips
            chips={msg.chips}
            onChip={onChip}
            disabled={chipsDisabled}
            actions={msg.suggestionActions}
          />
        )}
      </div>
    </div>
  );
}

function UserBubble({ msg }: { msg: UserMsg }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '14px', animation: 'vinbot-msg-in .35s ease both' }}>
      <div style={{
        background: t.navy, color: t.onNavy,
        borderRadius: '14px 4px 14px 14px', padding: '11px 14px',
        fontFamily: t.font, fontSize: '14px',
        lineHeight: 1.6, maxWidth: '75%',
      }}>
        {msg.text}
      </div>
    </div>
  );
}

// ─── Main ChatBot component ───────────────────────────────────────────────────

interface ChatBotProps {
  isOpen: boolean;
  onOpen: () => void;
  onClose: () => void;
  onRecommend: (query: RecoQuery) => void;
  onClearRecommend: () => void;
}

export function ChatBot({ isOpen, onOpen, onClose, onRecommend, onClearRecommend }: ChatBotProps) {
  const { token } = useAuth();
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [step, setStep] = useState(0);
  const [destType, setDestType] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [disabledChipMsgIds, setDisabledChipMsgIds] = useState<Set<string>>(new Set());
  // msgId → true (like) | false (dislike) | không có key = chưa bấm
  const [reactions, setReactions] = useState<Record<string, boolean>>({});
  const [showSatisfactionPopup, setShowSatisfactionPopup] = useState(false);
  const pendingResetRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const hasOpened = useRef(false);
  const sessionId = useRef(createSessionId());
  const sessionEnded = useRef(false);

  // Sync sessionId vào sessionStorage để HotelDetailModal đọc được
  useEffect(() => {
    sessionStorage.setItem('vinbot_session_id', sessionId.current);
  }, []);

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

  // Đóng bằng Escape (không khoá scroll nền — trang khách sạn bên trái vẫn cuộn được).
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
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

  const disableLastChips = (msgId: string) => {
    setDisabledChipMsgIds(prev => new Set([...prev, msgId]));
  };

  const sendBackendQuery = async (txt: string) => {
    setIsTyping(true);

    // ID cố định cho bot message — dùng để cập nhật text in-place khi stream
    const botMsgId = `${Date.now()}-bot-stream`;
    let msgCreated = false;
    let hasAnswerStarted = false;

    try {
      await sendChatMessageStream(
        {
          session_id: sessionId.current,
          query: txt,
          rerank_options: { top_k: 5 },
        },
        token,
        {
          onStatus(message) {
            if (!message || hasAnswerStarted) return;
            if (!msgCreated) {
              // Tạo status bubble lần đầu, ẩn TypingDots
              msgCreated = true;
              setIsTyping(false);
              setMessages(prev => [
                ...prev,
                { id: botMsgId, kind: 'bot' as const, text: message, isStatus: true },
              ]);
            } else {
              // Cập nhật nội dung status (giữ isStatus: true, icon đổi theo stage)
              setMessages(prev =>
                prev.map(m =>
                  m.id === botMsgId && m.kind === 'bot'
                    ? { ...m, text: message, isStatus: true }
                    : m,
                ),
              );
            }
          },
          onDelta(text) {
            if (!msgCreated) {
              // Delta đến trước status — tạo answer bubble luôn
              msgCreated = true;
              hasAnswerStarted = true;
              setIsTyping(false);
              setMessages(prev => [
                ...prev,
                { id: botMsgId, kind: 'bot' as const, text, isStatus: false },
              ]);
            } else if (!hasAnswerStarted) {
              // Delta đầu tiên — chuyển status bubble thành answer bubble
              hasAnswerStarted = true;
              setMessages(prev =>
                prev.map(m =>
                  m.id === botMsgId && m.kind === 'bot'
                    ? { ...m, text, isStatus: false }
                    : m,
                ),
              );
            } else {
              // Append token vào answer đang stream
              setMessages(prev =>
                prev.map(m =>
                  m.id === botMsgId && m.kind === 'bot'
                    ? { ...m, text: m.text + text }
                    : m,
                ),
              );
            }
          },
          onMetadata(data) {
            // Gắn suggestion chips sau khi answer hoàn tất
            const chips = suggestionChips(data);
            if (chips) {
              setMessages(prev =>
                prev.map(m =>
                  m.id === botMsgId && m.kind === 'bot'
                    ? { ...m, chips, suggestionActions: true }
                    : m,
                ),
              );
            }
            // Cập nhật danh sách khách sạn bên trái
            const hotels = hotelsFromBackend(data);
            if (hotels.length > 0) {
              onRecommend({ label: `VinBot · ${txt}`, params: {}, hotels });
            }
            setStep(3);
          },
          onDone() {
            setIsTyping(false);
            // Fallback nếu không nhận được delta nào (ví dụ pipeline trống)
            if (!msgCreated) {
              addBotMsg({
                kind: 'bot',
                text: 'Mình chưa tìm thấy câu trả lời phù hợp. Bạn có thể nói rõ hơn về điểm đến, ngày đi hoặc ngân sách không?',
              });
            } else if (!hasAnswerStarted) {
              setMessages(prev =>
                prev.map(m =>
                  m.id === botMsgId && m.kind === 'bot'
                    ? {
                      ...m,
                      text: 'Mình chưa tìm thấy câu trả lời phù hợp. Bạn có thể nói rõ hơn về điểm đến, ngày đi hoặc ngân sách không?',
                    }
                    : m,
                ),
              );
            }
          },
          onError(err) {
            setIsTyping(false);
            if (!msgCreated) {
              addBotMsg({
                kind: 'bot',
                text: err.message.startsWith('HTTP')
                  ? `Lỗi kết nối backend (${err.message}). Vui lòng thử lại.`
                  : `Mình chưa kết nối được backend: ${err.message}`,
                chips: ['Biển', 'Núi', 'Phố cổ', 'Vui chơi'],
              });
              setStep(1);
            }
          },
        },
      );
    } catch (err) {
      setIsTyping(false);
      if (!msgCreated) {
        addBotMsg({
          kind: 'bot',
          text: err instanceof Error
            ? `Mình chưa kết nối được backend: ${err.message}`
            : 'Mình chưa kết nối được backend. Vui lòng thử lại sau.',
          chips: ['Biển', 'Núi', 'Phố cổ', 'Vui chơi'],
        });
        setStep(1);
      }
    }
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
          text: `Tuyệt! ${dt} — mình đã lọc các khách sạn phù hợp ở danh sách bên trái. Ngân sách của bạn khoảng bao nhiêu?`,
          chips: ['Dưới 2 triệu', '2–5 triệu', 'Trên 5 triệu'],
        });
        onRecommend({ label: `Gợi ý · ${dt}`, params: { city: cityForDest(dt), sort_by: 'review_score:desc' } });
        setStep(2);
      }, 1300);
    } else if (step === 2) {
      setTimeout(() => {
        setIsTyping(false);
        addBotMsg({
          kind: 'bot',
          text: `Hoàn hảo! Mình đã cập nhật danh sách bên trái theo ngân sách ${chip}. Bạn có thể lọc/sắp xếp thêm tuỳ thích.`,
        });
        onRecommend({
          label: `${destType} · ${chip}`,
          params: { city: cityForDest(destType), sort_by: 'review_score:desc', ...budgetToPrice(chip) },
        });
        setStep(3);
        setTimeout(() => {
          addBotMsg({
            kind: 'bot',
            text: 'Bạn có muốn tìm thêm lựa chọn khác không?',
            chips: ['Bắt đầu lại', 'Liên hệ tư vấn viên'],
          });
        }, 600);
      }, 1400);
    } else if (chip.includes('Bắt đầu lại')) {
      handleReset();
    } else {
      void sendBackendQuery(chip);
    }
  };

  const handleSend = async () => {
    if (!input.trim()) return;
    const txt = input;
    setInput('');
    addUserMsg(txt);
    await sendBackendQuery(txt);
  };

  const handleReset = () => {
    // Nếu còn tin nhắn (không phải session rỗng), hiển thị popup hài lòng trước
    if (messages.length > 1 && !pendingResetRef.current) {
      pendingResetRef.current = true;
      setShowSatisfactionPopup(true);
      return;
    }
    _doReset();
  };

  const _doReset = useCallback(() => {
    pendingResetRef.current = false;
    // notify backend that current web session ended
    if (messages.length > 1) {
      void notifySessionEnd(sessionId.current, token);
      sessionEnded.current = true;
    }

    setMessages([]);
    setStep(0);
    setDestType('');
    setDisabledChipMsgIds(new Set());
    setReactions({});
    sessionId.current = createSessionId();
    sessionStorage.setItem('vinbot_session_id', sessionId.current);
    sessionEnded.current = false;
    onClearRecommend();
    hasOpened.current = false;
    setIsTyping(true);
    setTimeout(() => {
      hasOpened.current = true;
      setIsTyping(false);
      setMessages([STEP1_MSG]);
      setStep(1);
    }, 900);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length, token, onClearRecommend]);

  const handleSatisfactionReact = useCallback((value: boolean) => {
    const sid = sessionId.current;
    void logFinalReaction(sid, value, token);
    setShowSatisfactionPopup(false);
    _doReset();
  }, [token, _doReset]);

  const handleSatisfactionClose = useCallback(() => {
    setShowSatisfactionPopup(false);
    _doReset();
  }, [_doReset]);

  const handleReaction = useCallback((msgId: string, value: boolean) => {
    setReactions(prev => ({ ...prev, [msgId]: value }));
    void logReaction(sessionId.current, value, token);
  }, [token]);

  // send session end when user closes tab/window/reloads
  useEffect(() => {
    const onUnload = () => {
      if (!hasOpened.current || messages.length <= 1 || sessionEnded.current) {
        return;
      }
      void notifySessionEnd(sessionId.current, token);
      sessionEnded.current = true;
    };
    window.addEventListener('beforeunload', onUnload);
    window.addEventListener('pagehide', onUnload);
    return () => {
      window.removeEventListener('beforeunload', onUnload);
      window.removeEventListener('pagehide', onUnload);
    };
  }, [token, messages.length]);

  // when chat dock is closed (isOpen toggles false), notify session end
  // const prevOpen = useRef(isOpen);
  // useEffect(() => {
  //   if (prevOpen.current && !isOpen) {
  //     void notifySessionEnd(sessionId.current, token);
  //   }
  //   prevOpen.current = isOpen;
  // }, [isOpen, token]);

  return (
    <>
      {/* Satisfaction popup */}
      {showSatisfactionPopup && (
        <SatisfactionPopup
          onReact={handleSatisfactionReact}
          onClose={handleSatisfactionClose}
        />
      )}
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
          from { opacity: 0; transform: translateX(26px); }
          to   { opacity: 1; transform: none; }
        }
        @keyframes vinbot-pop {
          0%   { opacity: 0; transform: scale(0.96); }
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
          from { opacity: 0; transform: translateX(-28px); }
          to   { opacity: 1; transform: none; }
        }
        @keyframes vinbot-panel-right {
          from { opacity: 0; transform: translateX(28px); }
          to   { opacity: 1; transform: none; }
        }
        @keyframes vinbot-pulse-ring {
          0%   { transform: scale(1); opacity: 0.5; }
          100% { transform: scale(1.8); opacity: 0; }
        }
      `}</style>

      {/* Floating button */}
      <button
        onClick={onOpen}
        title="Hỏi VinBot"
        style={{
          position: 'fixed', bottom: '28px', right: '28px',
          width: '60px', height: '60px',
          background: t.navy, border: 'none',
          borderRadius: '18px', cursor: 'pointer',
          boxShadow: t.shadowLg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 999,
          transform: isOpen ? 'scale(0)' : 'scale(1)',
          transition: 'transform 0.25s cubic-bezier(0.34,1.56,0.64,1)',
        }}
      >
        {!isOpen && (
          <span style={{
            position: 'absolute', inset: 0, borderRadius: '18px',
            border: `2px solid ${t.accent}`,
            animation: 'vinbot-pulse-ring 1.8s ease-out infinite',
          }} />
        )}
        <svg width="31" height="31" viewBox="0 0 32 32" fill="none" aria-hidden="true">
          <path
            d="M6.5 7.5C6.5 5.8 7.8 4.5 9.5 4.5H22.5C24.2 4.5 25.5 5.8 25.5 7.5V17.8C25.5 19.5 24.2 20.8 22.5 20.8H16.4L10.2 26.2V20.8H9.5C7.8 20.8 6.5 19.5 6.5 17.8V7.5Z"
            fill="#FFFFFF"
          />
          <path d="M11 11.2H21" stroke={t.navy} strokeWidth="2" strokeLinecap="round" />
          <path d="M11 15.4H17.5" stroke={t.navy} strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>

      {/* Chat dock — sidebar phải; trang Khách sạn vẫn ở bên trái và dùng được */}
      {isOpen && (
        <div
          style={{
            position: 'fixed', top: 0, right: 0, bottom: 0, width: `${CHAT_DOCK_WIDTH}px`, zIndex: 90,
            background: t.bg,
            borderLeft: `1px solid ${t.borderStrong}`,
            boxShadow: '-16px 0 50px rgba(28,27,25,0.10)',
            display: 'flex', flexDirection: 'column',
            overflow: 'hidden',
            animation: 'vinbot-panel-right 0.3s ease both',
          }}
        >
          {/* Header */}
          <div style={{
            background: t.surface,
            padding: '16px 18px',
            display: 'flex', alignItems: 'center', gap: '12px',
            borderBottom: `1px solid ${t.border}`,
            flexShrink: 0,
          }}>
            <div style={{ position: 'relative' }}>
              <BotAvatar size={42} />
              <span style={{
                position: 'absolute', bottom: '0px', right: '0px',
                width: '10px', height: '10px', background: '#22C55E',
                borderRadius: '50%', border: '2px solid white',
              }} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: t.font, fontSize: '17px', fontWeight: 700, color: t.ink }}>
                VinBot
              </div>
              <div style={{ fontFamily: t.font, fontSize: '12px', color: t.ink3 }}>
                Trợ lý du lịch của bạn • Phản hồi ngay
              </div>
            </div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <IconBtn label="Cuộc hội thoại mới" onClick={handleReset}>↺</IconBtn>
              <IconBtn label="Đóng" onClick={onClose}>✕</IconBtn>
            </div>
          </div>

          {/* Journey progress bar */}
          <div style={{ background: t.surface, padding: '10px 18px', borderBottom: `1px solid ${t.border}`, display: 'flex', gap: '8px', alignItems: 'center', flexShrink: 0 }}>
            {['Loại hình', 'Điểm đến', 'Gói du lịch'].map((label, i) => {
              const active = step > i;
              const current = step === i + 1;
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1 }}>
                  <div style={{
                    width: '22px', height: '22px', borderRadius: '50%', flexShrink: 0,
                    background: active ? t.navy : current ? t.accentSoft : t.surface,
                    border: `1.5px solid ${active ? t.navy : current ? t.accent : t.border}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontFamily: t.font, fontSize: '11px', fontWeight: 600,
                    color: active ? '#FFFFFF' : current ? t.accentDark : t.ink3,
                    transition: 'all .3s',
                  }}>
                    {active ? '✓' : i + 1}
                  </div>
                  <span style={{ fontFamily: t.font, fontSize: '11px', fontWeight: 500, color: active || current ? t.ink : t.ink3, whiteSpace: 'nowrap' }}>
                    {label}
                  </span>
                  {i < 2 && <div style={{ flex: 1, height: '1.5px', background: active ? t.navy : t.border, transition: 'background .3s' }} />}
                </div>
              );
            })}
          </div>

          {/* Messages + gợi ý inline */}
          <div
            ref={scrollRef}
            className="no-scrollbar"
            style={{ flex: 1, overflowY: 'auto', padding: '18px', display: 'flex', flexDirection: 'column', gap: '0' }}
          >
            {messages.map(msg =>
              msg.kind === 'user'
                ? <UserBubble key={msg.id} msg={msg} />
                : <BotBubble
                  key={msg.id}
                  msg={msg}
                  onChip={(chip) => handleChip(chip, msg.id)}
                  chipsDisabled={disabledChipMsgIds.has(msg.id)}
                  onReact={handleReaction}
                  reacted={msg.id in reactions ? reactions[msg.id] : null}
                  isWelcome={msg.id === WELCOME_MSG_ID}
                />
            )}
            {isTyping && <TypingDots />}
            <div style={{ height: '4px' }} />
          </div>

          {/* Input bar */}
          <div style={{
            padding: '12px 14px',
            borderTop: `1px solid ${t.border}`,
            background: t.surface,
            display: 'flex', gap: '8px', alignItems: 'center',
            flexShrink: 0,
          }}>
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.nativeEvent.isComposing && handleSend()}
              placeholder="Nhập tin nhắn hoặc chọn gợi ý bên trên..."
              style={{
                flex: 1, padding: '11px 14px',
                border: `1px solid ${t.border}`, borderRadius: t.rPill,
                fontFamily: t.font, fontSize: '14px',
                color: t.ink, background: t.bg, outline: 'none',
                transition: 'border-color .2s',
              }}
              onFocus={e => (e.target.style.borderColor = t.accent)}
              onBlur={e => (e.target.style.borderColor = t.border)}
            />
            <button
              onClick={handleSend}
              title="Gửi"
              style={{
                width: '40px', height: '40px', borderRadius: '50%',
                background: t.navy, border: 'none',
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0, transition: 'background .15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = t.navyHover)}
              onMouseLeave={e => (e.currentTarget.style.background = t.navy)}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M22 2L11 13" stroke="white" strokeWidth="2.2" strokeLinecap="round" />
                <path d="M22 2L15 22L11 13L2 9L22 2Z" fill="white" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function IconBtn({ children, label, onClick }: { children: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title={label}
      style={{
        background: t.bgSoft, border: 'none', borderRadius: '10px',
        width: '34px', height: '34px', cursor: 'pointer', color: t.ink2,
        fontSize: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center',
        transition: 'background .15s, color .15s',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = t.border; e.currentTarget.style.color = t.ink; }}
      onMouseLeave={e => { e.currentTarget.style.background = t.bgSoft; e.currentTarget.style.color = t.ink2; }}
    >
      {children}
    </button>
  );
}
