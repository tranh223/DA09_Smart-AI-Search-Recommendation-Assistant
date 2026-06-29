import { useState, useEffect } from 'react';
import { HomePage } from './pages/HomePage';
import { HotelsPage } from './pages/HotelsPage';
import { AdminPage } from './pages/AdminPage';
import { AuthPage } from './pages/AuthPage';
import { Dashboard } from './pages/Dashboard';
import { ChatBot } from './components/chat/ChatBot';
import { type HotelListParams, type RecoQuery } from './services/hotels';
import { type Route } from './components/layout/NavBar';
import { useAuth } from './hooks/useAuth';

export default function App() {
  const { user, role } = useAuth();
  const [path, setPath] = useState<string>(() => (typeof window !== 'undefined' ? window.location.pathname : '/'));
  useEffect(() => {
    const handler = () => setPath(window.location.pathname);
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, []);
  const [route, setRoute] = useState<Route>('home');
  const [chatOpen, setChatOpen] = useState(false);
  const [recoQuery, setRecoQuery] = useState<RecoQuery | null>(null);
  const [hotelSearch, setHotelSearch] = useState<HotelListParams | null>(null);

  // ── Authentication Check ───────────────────────────────────────────────────
  // Nếu chưa đăng nhập, chỉ cho phép xem trang Đăng nhập / Đăng ký.
  if (!user) {
    return <AuthPage />;
  }

  // Mở chat luôn đưa người dùng về trang Khách sạn để bên trái là danh sách khách sạn.
  const openChat = () => {
    setRoute('hotels');
    setChatOpen(true);
  };

  const searchHotels = (params: HotelListParams) => {
    setRecoQuery(null);
    setHotelSearch(params);
    setRoute('hotels');
  };

  // ── Admin role → trang quản trị or dashboard ─────────────────────────────
  if (role === 'admin') {
    if (path.startsWith('/dashboard')) {
      return <Dashboard />;
    }
    return <AdminPage onNavigate={setRoute} />;
  }

  // ── User role → app bình thường ─────────────────────────────────────────────
  return (
    <>
      {route === 'hotels'
        ? <HotelsPage onNavigate={setRoute} chatOpen={chatOpen} recoQuery={recoQuery} initialFilters={hotelSearch} />
        : <HomePage onNavigate={setRoute} onOpenChat={openChat} onSearchHotels={searchHotels} chatOpen={chatOpen} />}
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
