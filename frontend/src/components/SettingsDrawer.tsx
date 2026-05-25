"use client";

import { useState, useEffect } from "react";
import { X, Save, Loader2 } from "lucide-react";
import { authHeaders } from "@/lib/auth";

interface Profile {
  name: string;
  job_title: string;
  niche: string;
  tone: string;
  linkedin_headline: string;
  bio: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSaved: (profile: Profile) => void;
}

export default function SettingsDrawer({ open, onClose, onSaved }: Props) {
  const [form, setForm] = useState<Profile>({
    name: "", job_title: "", niche: "", tone: "", linkedin_headline: "", bio: "",
  });
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    fetch("http://127.0.0.1:8000/profile", { headers: authHeaders() })
      .then((r) => r.json())
      .then((data) => {
        if (data && !data.detail) {
          setForm({
            name: data.name || "",
            job_title: data.job_title || "",
            niche: data.niche || "",
            tone: data.tone || "",
            linkedin_headline: data.linkedin_headline || "",
            bio: data.bio || "",
          });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(form),
      });
      if (res.ok) {
        onSaved(form);
        onClose();
      }
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md glass rounded-l-2xl p-6 overflow-y-auto shadow-2xl border-l border-white/10 animate-in slide-in-from-right">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-base font-semibold text-white tracking-[-0.02em]">Your Profile</h2>
          <button onClick={onClose} className="text-white/40 hover:text-white/80 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin text-white/40" /></div>
        ) : (
          <div className="flex flex-col gap-3">
            {(["name", "job_title", "niche", "tone", "linkedin_headline", "bio"] as const).map((field) => (
              <div key={field} className="flex flex-col gap-1">
                <label className="text-[10px] uppercase tracking-[0.12em] font-semibold text-white/40">
                  {field.replace(/_/g, " ")}
                  {field === "name" && <span className="text-red-400 ml-1">*</span>}
                </label>
                {field === "bio" ? (
                  <textarea
                    value={form[field]}
                    onChange={(e) => setForm({ ...form, [field]: e.target.value })}
                    rows={3}
                    className="w-full rounded-xl text-[13px] text-white bg-white/5 border border-white/10 p-3 outline-none focus:border-white/20 resize-none"
                    placeholder={`Your ${field.replace(/_/g, " ")}`}
                  />
                ) : (
                  <input
                    type="text"
                    value={form[field]}
                    onChange={(e) => setForm({ ...form, [field]: e.target.value })}
                    className="w-full h-9 rounded-xl text-[13px] text-white bg-white/5 border border-white/10 px-3 outline-none focus:border-white/20"
                    placeholder={`Your ${field.replace(/_/g, " ")}`}
                    required={field === "name"}
                  />
                )}
              </div>
            ))}

            <button
              onClick={handleSave}
              disabled={saving || !form.name.trim()}
              className="mt-3 w-full h-9 rounded-xl flex items-center justify-center gap-2 text-[13px] font-semibold bg-white text-[oklch(0.10_0.008_248)] hover:bg-white/92 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {saving ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Saving...</>
                : <><Save className="w-3.5 h-3.5" /> Save Profile</>}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
