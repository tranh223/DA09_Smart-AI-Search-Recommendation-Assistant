import { useState } from "react";

import ChatWindow from "./components/ChatWindow";
import Login from "./components/Login";

const STORAGE_KEY = "user_id";

export default function App() {
  const [userId, setUserId] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY));

  const login = (id: string) => {
    localStorage.setItem(STORAGE_KEY, id);
    setUserId(id);
  };

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY);
    setUserId(null);
  };

  if (!userId) return <Login onLogin={login} />;

  return (
    <div className="flex h-screen flex-col bg-slate-50">
      <header className="flex items-center gap-3 bg-gradient-to-r from-blue-500 to-blue-600 px-5 py-4 text-white shadow-sm">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-white/20 text-xl">✈️</span>
        <div className="flex-1">
          <h1 className="text-base font-semibold leading-tight">Travel Assistant</h1>
          <p className="text-xs text-blue-100">OTA · gợi ý khách sạn cá nhân hóa</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="rounded-full bg-white/20 px-3 py-1">👤 {userId}</span>
          <button
            onClick={logout}
            className="rounded-full bg-white/10 px-3 py-1 transition hover:bg-white/20"
          >
            Đổi user
          </button>
        </div>
      </header>
      <main className="flex-1 overflow-hidden">
        <ChatWindow key={userId} />
      </main>
    </div>
  );
}
