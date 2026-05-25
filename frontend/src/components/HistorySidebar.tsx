"use client";

import { useState, useEffect } from "react";
import { Clock, Trash2, Archive, Copy, RotateCcw, X, Loader2, PlaySquare, FileText } from "lucide-react";
import { authHeaders } from "@/lib/auth";

interface Generation {
  id: string;
  source_url: string | null;
  source_type: string;
  generated_post: string;
  status: string;
  created_at: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSelect: (gen: Generation) => void;
  refreshKey: number;
}

export default function HistorySidebar({ open, onClose, onSelect, refreshKey }: Props) {
  const [generations, setGenerations] = useState<Generation[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/generations", { headers: authHeaders() });
      if (res.ok) setGenerations(await res.json());
    } catch {} finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) load();
  }, [open, refreshKey]);

  const handleDelete = async (id: string) => {
    const res = await fetch(`http://127.0.0.1:8000/generations/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (res.ok) setGenerations((prev) => prev.filter((g) => g.id !== id));
  };

  const handleArchive = async (id: string) => {
    const res = await fetch(`http://127.0.0.1:8000/generations/${id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ status: "archived" }),
    });
    if (res.ok) load();
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  };

  const firstLine = (post: string) => {
    const line = post.split("\n")[0];
    return line.length > 80 ? line.slice(0, 80) + "..." : line;
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-start">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-sm glass rounded-r-2xl p-5 overflow-y-auto shadow-2xl border-r border-white/10 animate-in slide-in-from-left">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-white/50" />
            <h2 className="text-sm font-semibold text-white tracking-[-0.02em]">History</h2>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white/80 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

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

                  <div className="hidden group-hover:flex items-center gap-1 shrink-0">
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
                      onClick={(e) => { e.stopPropagation(); handleArchive(gen.id); }}
                      title="Archive"
                      className="p-1 rounded-md text-white/30 hover:text-yellow-400 hover:bg-yellow-500/10 transition-all"
                    ><Archive className="w-3 h-3" /></button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(gen.id); }}
                      title="Delete"
                      className="p-1 rounded-md text-white/30 hover:text-red-400 hover:bg-red-500/10 transition-all"
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
