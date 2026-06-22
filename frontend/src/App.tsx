import { useState } from 'react';
import { HomePage } from './pages/HomePage';
import { HotelsPage } from './pages/HotelsPage';
import { AdminPage } from './pages/AdminPage';
import { ChatBot } from './components/chat/ChatBot';
import { type RecoQuery } from './services/hotels';
import { type Route } from './components/layout/NavBar';
import { useAuth } from './hooks/useAuth';

export default function App() {
  const { role } = useAuth();
  const [route, setRoute] = useState<Route>('home');
  const [chatOpen, setChatOpen] = useState(false);
  // Gợi ý của VinBot dưới dạng truy vấn API — hiển thị ở lưới trang Khách sạn.
  const [recoQuery, setRecoQuery] = useState<RecoQuery | null>(null);

  // Mở chat luôn đưa người dùng về trang Khách sạn để bên trái là danh sách khách sạn.
  const openChat = () => {
    setRoute('hotels');
    setChatOpen(true);
  };

  // ── Admin role → trang quản trị ─────────────────────────────────────────────
  if (role === 'admin') {
    return <AdminPage onNavigate={setRoute} />;
  }

  // ── User role (hoặc chưa đăng nhập) → app bình thường ──────────────────────
  return (
    <>
      {route === 'hotels'
        ? <HotelsPage onNavigate={setRoute} chatOpen={chatOpen} recoQuery={recoQuery} />
        : <HomePage onNavigate={setRoute} onOpenChat={openChat} chatOpen={chatOpen} />}
      <ChatBot
        isOpen={chatOpen}
        onOpen={openChat}
        onClose={() => setChatOpen(false)}
        onRecommend={setRecoQuery}
        onClearRecommend={() => setRecoQuery(null)}
      />
    </>
  );
}
