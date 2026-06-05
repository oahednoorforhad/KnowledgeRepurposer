"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Zap, Loader2, ArrowRight } from "lucide-react";
// Cookie-based auth — token managed via HTTP-only cookie

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`http://127.0.0.1:8000/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Something went wrong");
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen w-full flex flex-col items-center justify-center px-5 relative overflow-hidden">
      <div aria-hidden className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, oklch(0.55 0.22 255 / 0.13) 0%, transparent 70%)", filter: "blur(80px)" }}
      />
      <div aria-hidden className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, oklch(0.50 0.18 280 / 0.10) 0%, transparent 70%)", filter: "blur(80px)" }}
      />

      <div className="chip mx-auto mb-6">
        <Zap className="w-3 h-3" />
        AI Content Engine
      </div>

      <div className="w-full max-w-sm rounded-2xl glass p-8 relative z-10">
        <h1 className="text-xl font-semibold text-white text-center mb-6 tracking-[-0.02em]">
          {mode === "login" ? "Welcome back" : "Create account"}
        </h1>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-[0.12em] font-semibold text-white/40">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full h-10 px-3.5 rounded-xl text-[13.5px] text-white bg-white/5 border border-white/10 outline-none focus:border-white/20 focus:bg-white/8 transition-all"
              placeholder="you@example.com"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-[0.12em] font-semibold text-white/40">Password</label>
            <input
              type="password"
              required
              minLength={10}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full h-10 px-3.5 rounded-xl text-[13.5px] text-white bg-white/5 border border-white/10 outline-none focus:border-white/20 focus:bg-white/8 transition-all"
              placeholder="At least 10 characters"
            />
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-red-500/8 border border-red-500/20 text-red-400 text-[13px]">{error}</div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full h-10 rounded-xl flex items-center justify-center gap-2 text-[13.5px] font-semibold transition-all duration-200 bg-white text-[oklch(0.10_0.008_248)] hover:bg-white/92 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Processing...</>
              : <>{mode === "login" ? "Sign In" : "Create Account"} <ArrowRight className="w-4 h-4" /></>}
          </button>
        </form>

        <p className="text-center mt-5 text-[12.5px] text-white/30">
          {mode === "login" ? "Don't have an account?" : "Already have an account?"}{" "}
          <button
            onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
            className="text-white/60 hover:text-white/80 underline underline-offset-2 transition-colors"
          >
            {mode === "login" ? "Register" : "Sign in"}
          </button>
        </p>
      </div>
    </main>
  );
}
