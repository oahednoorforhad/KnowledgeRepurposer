"use client";

import { useState, useEffect } from "react";
import { Clock, Trash2, Archive, CheckCircle2, Copy, RotateCcw, X, Loader2, PlaySquare, FileText } from "lucide-react";
import { apiFetch } from "@/lib/auth";

interface Generation {
  id: string;
  source_url: string | null;
  source_type: string;
  generated_post: string;
  status: string;
  created_at: string;
}

// Mounted only while open, so each open starts fresh in the loading state.
interface Props {
  onClose: () => void;
  onSelect: (gen: Generation) => void;
}

export default function HistorySidebar({ onClose, onSelect }: Props) {
  const [generations, setGenerations] = useState<Generation[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set());

  // One status/delete request per item at a time.
  const withBusy = async (id: string, action: () => Promise<void>) => {
    if (busyIds.has(id)) return;
    setBusyIds((prev) => new Set(prev).add(id));
    try {
      await action();
    } finally {
      setBusyIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
    }
  };
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    let cancelled = false;
    apiFetch("/generations")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => { if (!cancelled && data) setGenerations(data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const handleDelete = (id: string) => withBusy(id, async () => {
    setActionError("");
    try {
      const res = await apiFetch(`/generations/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error();
      setGenerations((prev) => prev.filter((g) => g.id !== id));
    } catch {
      setActionError("Couldn't delete that post. Please retry.");
    }
  });

  const handleStatus = (id: string, status: "published" | "archived") => withBusy(id, async () => {
    setActionError("");
    try {
      const res = await apiFetch(`/generations/${id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error();
      const updated: Generation = await res.json();
      setGenerations((prev) => prev.map((g) => (g.id === id ? updated : g)));
    } catch {
      setActionError("Couldn't update that post. Please retry.");
    }
  });

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  };

  const firstLine = (post: string) => {
    const line = post.split("\n")[0];
    return line.length > 80 ? line.slice(0, 80) + "..." : line;
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-start">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div role="dialog" aria-modal="true" aria-label="History" className="relative w-full max-w-sm glass rounded-r-2xl p-5 overflow-y-auto shadow-2xl border-r border-white/10 animate-in slide-in-from-left">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-white/50" />
            <h2 className="text-sm font-semibold text-white tracking-[-0.02em]">History</h2>
          </div>
          <button onClick={onClose} aria-label="Close" className="text-white/40 hover:text-white/80 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {actionError && <p role="alert" className="text-[12px] text-red-400 mb-3">{actionError}</p>}

        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin text-white/40" /></div>
        ) : generations.length === 0 ? (
          <p className="text-[13px] text-white/25 text-center py-12">No generations yet</p>
        ) : (
          <div className="flex flex-col gap-2">
            {generations.map((gen) => (
              <div
                key={gen.id}
                onClick={() => onSelect(gen)}
                className="group p-3 rounded-xl bg-white/[0.04] border border-white/[0.06] hover:bg-white/[0.08] cursor-pointer transition-all"
              >
                <div className="flex items-start gap-2.5">
                  <div className="mt-0.5 shrink-0">
                    {gen.source_type === "youtube" ? (
                      <PlaySquare className="w-3.5 h-3.5 text-white/30" />
                    ) : (
                      <FileText className="w-3.5 h-3.5 text-white/30" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[12.5px] text-white/70 font-light truncate leading-snug">
                      {firstLine(gen.generated_post)}
                    </p>
                    <div className="flex items-center gap-2 mt-1.5">
                      <span className="text-[10px] text-white/25">{formatDate(gen.created_at)}</span>
                      <span className={"text-[9px] px-1.5 py-0.5 rounded-full " + (
                        gen.status === "published" ? "bg-green-500/10 text-green-400"
                        : gen.status === "archived" ? "bg-yellow-500/10 text-yellow-400"
                        : "bg-white/5 text-white/30"
                      )}>{gen.status}</span>
                    </div>
                  </div>

                  <div className="hidden group-hover:flex group-focus-within:flex items-center gap-1 shrink-0">
                    <button
                      onClick={(e) => { e.stopPropagation(); onSelect(gen); onClose(); }}
                      title="Re-run"
                      className="p-1 rounded-md text-white/30 hover:text-white/80 hover:bg-white/10 transition-all"
                    ><RotateCcw className="w-3 h-3" /></button>
                    <button
                      onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(gen.generated_post); }}
                      title="Copy"
                      className="p-1 rounded-md text-white/30 hover:text-white/80 hover:bg-white/10 transition-all"
                    ><Copy className="w-3 h-3" /></button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleStatus(gen.id, "published"); }}
                      disabled={busyIds.has(gen.id)}
                      title="Mark published"
                      className="p-1 rounded-md text-white/30 hover:text-green-400 hover:bg-green-500/10 disabled:opacity-40 transition-all"
                    ><CheckCircle2 className="w-3 h-3" /></button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleStatus(gen.id, "archived"); }}
                      disabled={busyIds.has(gen.id)}
                      title="Archive"
                      className="p-1 rounded-md text-white/30 hover:text-yellow-400 hover:bg-yellow-500/10 disabled:opacity-40 transition-all"
                    ><Archive className="w-3 h-3" /></button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(gen.id); }}
                      disabled={busyIds.has(gen.id)}
                      title="Delete"
                      className="p-1 rounded-md text-white/30 hover:text-red-400 hover:bg-red-500/10 disabled:opacity-40 transition-all"
                    ><Trash2 className="w-3 h-3" /></button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
