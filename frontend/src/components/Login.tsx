import { useState } from "react";

// "Đăng nhập" tạm thời: nhập user_id để định danh người dùng (chưa có auth thật).
export default function Login({ onLogin }: { onLogin: (userId: string) => void }) {
  const [value, setValue] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const id = value.trim();
    if (id) onLogin(id);
  };

  return (
    <div className="flex h-screen items-center justify-center bg-slate-50 p-6">
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-5 rounded-2xl border border-slate-200 bg-white p-7 shadow-lg"
      >
        <div className="text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 text-3xl text-white shadow-lg">
            ✈️
          </div>
          <h1 className="mt-3 text-lg font-semibold text-slate-800">Travel Assistant</h1>
          <p className="mt-1 text-sm text-slate-500">
            Nhập <b>user ID</b> để bắt đầu nhận gợi ý cá nhân hóa.
          </p>
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-slate-600">User ID</label>
          <input
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="vd: user_141"
            className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-blue-100"
          />
        </div>

        <button
          type="submit"
          disabled={!value.trim()}
          className="w-full rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Vào
        </button>

        <p className="text-center text-[11px] text-slate-400">
          Đăng nhập tạm thời — không cần mật khẩu.
        </p>
      </form>
    </div>
  );
}
