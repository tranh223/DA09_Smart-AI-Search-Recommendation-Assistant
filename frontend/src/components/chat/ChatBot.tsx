import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { t } from '../../styles/theme';
import { sendChatMessageStream, type BackendChatData } from '../../services/backendApi';
import { type Hotel, type RecoQuery, extractImages } from '../../services/hotels';
import { useAuth } from '../../hooks/useAuth';

// Bề rộng chat dock bên phải — trang chừa đúng khoảng này để không bị che.
export const CHAT_DOCK_WIDTH = 440;

// ─── Types ────────────────────────────────────────────────────────────────────

interface BotMsg {
  id: string;
  kind: 'bot';
  text: string;
  chips?: string[];
  /** true khi bubble đang hiển thị status pipeline, false/undefined khi là answer thật */
  isStatus?: boolean;
}

interface UserMsg {
  id: string;
  kind: 'user';
  text: string;
}

type ChatMsg = BotMsg | UserMsg;

const STEP1_MSG: BotMsg = {
  id: 'step1',
  kind: 'bot',
  text: 'Xin chào! Mình là VinBot — trợ lý du lịch thông minh của VinJourney. Bạn muốn đi dạng nào?',
  chips: ['Tìm resort gần biển', 'Khách sạn cho gia đình', 'Gần trung tâm', 'Có hồ bơi'],
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
    .slice(0, 4);
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
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
      <circle cx="24" cy="24" r="23" fill={t.ink} />
      {/* mắt trắng */}
      <circle cx="18.5" cy="21.5" r="2.3" fill="#FFFFFF" />
      <circle cx="29.5" cy="21.5" r="2.3" fill="#FFFFFF" />
      {/* miệng cười trắng */}
      <path d="M17.5 28 Q24 33.5 30.5 28" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" fill="none" />
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

function QuickReplyChips({ chips, onChip, disabled }: { chips: string[]; onChip: (c: string) => void; disabled: boolean }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '10px' }}>
      {chips.map(chip => (
        <button
          key={chip}
          onClick={() => !disabled && onChip(chip)}
          disabled={disabled}
          style={{
            fontFamily: t.font, fontSize: '13px', fontWeight: 500,
            color: disabled ? t.ink3 : t.ink,
            border: `1px solid ${disabled ? t.border : t.borderStrong}`,
            borderRadius: t.rPill, padding: '6px 14px',
            background: disabled ? t.bgSoft : t.surface,
            cursor: disabled ? 'default' : 'pointer',
            transition: 'background .15s, border-color .15s',
          }}
          onMouseEnter={e => { if (!disabled) { e.currentTarget.style.background = t.accentSoft; e.currentTarget.style.borderColor = t.accent; } }}
          onMouseLeave={e => { if (!disabled) { e.currentTarget.style.background = t.surface; e.currentTarget.style.borderColor = t.borderStrong; } }}
        >
          {chip}
        </button>
      ))}
    </div>
  );
}

// ── Status stage helpers ──────────────────────────────────────────────────────

function getStatusIcon(message: string): string {
  if (message.includes('phân tích')) return '🔍';
  if (message.includes('tìm kiếm')) return '🏨';
  if (message.includes('xử lý') || message.includes('xếp hạng')) return '⚙️';
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

function BotBubble({
  msg, onChip, chipsDisabled,
}: { msg: BotMsg; onChip: (c: string) => void; chipsDisabled: boolean }) {
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
  const [isTyping, setIsTyping] = useState(false);
  const [disabledChipMsgIds, setDisabledChipMsgIds] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);
  const hasOpened = useRef(false);
  const sessionId = useRef(createSessionId());

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
                  m.id === botMsgId && m.kind === 'bot' ? { ...m, chips } : m,
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
                chips: STEP1_MSG.chips,
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
          chips: STEP1_MSG.chips,
        });
        setStep(1);
      }
    }
  };

  const handleChip = (chip: string, fromMsgId: string) => {
    disableLastChips(fromMsgId);
    addUserMsg(chip);

    if (chip.includes('Bắt đầu lại')) {
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
    setMessages([]);
    setStep(0);
    setDisabledChipMsgIds(new Set());
    sessionId.current = createSessionId();
    onClearRecommend();
    hasOpened.current = false;
    setIsTyping(true);
    setTimeout(() => {
      hasOpened.current = true;
      setIsTyping(false);
      setMessages([STEP1_MSG]);
      setStep(1);
    }, 900);
  };

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
        <svg width="28" height="28" viewBox="0 0 30 30" fill="none">
          <rect x="3" y="3" width="24" height="18" rx="6" fill="#FFFFFF" />
          <circle cx="10" cy="12" r="2" fill={t.navy} />
          <circle cx="15" cy="12" r="2" fill={t.navy} />
          <circle cx="20" cy="12" r="2" fill={t.navy} />
          <path d="M10 21 L10 27 L16 21Z" fill="#FFFFFF" />
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
