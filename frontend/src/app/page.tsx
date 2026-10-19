"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import {
  Sparkles, ArrowRight, Loader2, PlaySquare, Copy, Check, Zap, FileUp, Link2, X, Settings, Clock, Pencil,
} from "lucide-react";
import { apiFetch } from "@/lib/auth";
import { readNdjson } from "@/lib/ndjson";
import SettingsDrawer from "@/components/SettingsDrawer";
import HistorySidebar from "@/components/HistorySidebar";

const VARIANT_SEPARATOR = "---VARIANT---"; // must match app/services/llm.py
const REFINE_PRESETS = ["Shorter", "More casual", "Stronger hook"];

function splitVersions(text: string) {
  // Drop a separator that is still arriving mid-stream (e.g. "---VAR") so it never renders.
  for (let n = VARIANT_SEPARATOR.length - 1; n >= 3; n--) {
    if (text.endsWith(VARIANT_SEPARATOR.slice(0, n))) {
      text = text.slice(0, -n);
      break;
    }
  }
  return text.split(VARIANT_SEPARATOR).map((v) => v.trim()).filter(Boolean);
}

type GenerateEvent ={ delta?: string; done?: boolean; generation_ids?: string[]; error?: string };

// FastAPI 422s carry a list in `detail`; only show it when it is a plain message.
async function errorDetail(res: Response, fallback: string): Promise<string> {
  const data = await res.json().catch(() => null);
  return typeof data?.detail === "string" ? data.detail : fallback;
}

function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(" ");
}

function Label({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cn("label-caps", className)}>{children}</p>;
}

function GlassCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("glass rounded-2xl", className)}>{children}</div>;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handleCopy}
      title="Copy to clipboard"
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200",
        copied
          ? "bg-green-500/15 text-green-400 border border-green-500/30"
          : "bg-white/5 text-white/50 border border-white/10 hover:bg-white/10 hover:text-white/80"
      )}
    >
      {copied ? <><Check className="w-3.5 h-3.5" /> Copied</> : <><Copy className="w-3.5 h-3.5" /> Copy</>}
    </button>
  );
}

function SkeletonBlock({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "rounded-md animate-pulse",
        "bg-gradient-to-r from-white/4 via-white/8 to-white/4",
        "bg-[length:200%_100%] animate-[shimmer_1.8s_ease_infinite]",
        className
      )}
    />
  );
}

export default function Home() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [inputMode, setInputMode] = useState<"url" | "pdf">("url");
  const [url, setUrl] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState("");
  const [variants, setVariants] = useState<1 | 3>(1);
  const [loading, setLoading] = useState(false);
  const [post, setPost] = useState("");
  const [error, setError] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [refreshHistory, setRefreshHistory] = useState(0);
  const [profileComplete, setProfileComplete] = useState(false);
  const [activeVersion, setActiveVersion] = useState(0);
  const [generationIds, setGenerationIds] = useState<string[]>([]);

  // While streaming, versions appear one by one as the separator arrives.
  const versions = splitVersions(post);
  const activeIndex = Math.min(activeVersion, Math.max(versions.length - 1, 0));
  const shown = versions[activeIndex] ?? "";
  // Legacy history rows hold several versions joined into one row; only edit when ids map 1:1.
  const activeId = versions.length === generationIds.length ? generationIds[activeIndex] : undefined;

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);

  const replaceVersion = (index: number, text: string) =>
    setPost((prev) => {
      const parts = prev.split(VARIANT_SEPARATOR).map((v) => v.trim()).filter(Boolean);
      parts[index] = text;
      return parts.join(`\n${VARIANT_SEPARATOR}\n`);
    });

  const [refining, setRefining] = useState(false);
  const [refineText, setRefineText] = useState("");
  // Bumped when a new generation or history item replaces the view, so in-flight
  // edit/refine requests don't write into a post they no longer belong to.
  const viewToken = useRef(0);

  const handleRefine = async (instruction: string) => {
    const index = activeIndex;
    const original = shown;
    const id = activeId;
    const token = viewToken.current;
    const current = () => viewToken.current === token;
    setError("");
    setRefining(true);
    try {
      const res = await apiFetch(`/generations/${id}/refine`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction }),
      });
      if (!res.ok) throw new Error(await errorDetail(res, "Failed to refine post."));
      let text = "";
      let streamError = "";
      let done = false;
      await readNdjson<GenerateEvent>(res, (event) => {
        if (event.delta) {
          text += event.delta;
          // A whitespace-only version would be filtered out and shift the indices.
          if (text.trim() && current()) replaceVersion(index, text);
        } else if (event.error) streamError = event.error;
        else if (event.done) done = true;
      });
      if (streamError) throw new Error(streamError);
      if (!done) throw new Error("Refine was interrupted. Please retry.");
      if (!current()) return;
      setRefineText("");
      setRefreshHistory((n) => n + 1);
    } catch (err: unknown) {
      if (!current()) return;
      replaceVersion(index, original);
      setError(err instanceof Error ? err.message : "Failed to refine post.");
    } finally {
      setRefining(false);
    }
  };

  const handleSaveEdit = async () => {
    const token = viewToken.current;
    setSavingEdit(true);
    try {
      const res = await apiFetch(`/generations/${activeId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ generated_post: draft }),
      });
      if (!res.ok) throw new Error(await errorDetail(res, "Failed to save your edit."));
      if (viewToken.current !== token) return;
      replaceVersion(activeIndex, draft.trim());
      setEditing(false);
      setRefreshHistory((n) => n + 1);
    } catch (err: unknown) {
      if (viewToken.current !== token) return;
      setError(err instanceof Error ? err.message : "Failed to save your edit.");
    } finally {
      setSavingEdit(false);
    }
  };

  useEffect(() => {
    apiFetch("/profile")
      .then((r) => {
        if (!r.ok) throw new Error("Not authenticated");
        return r.json();
      })
      .then((data) => {
        if (data && data.name) setProfileComplete(true);
      })
      .catch(() => {
        router.replace("/login");
      })
      .finally(() => setReady(true));
  }, [router]);

  const handleModeSwitch = (mode: "url" | "pdf") => {
    setInputMode(mode);
    setError("");
    setUrl("");
    setPdfFile(null);
  };

  const handleGenerate = async () => {
    if (loading || refining) return;
    if (inputMode === "url" && !url) {
      setError("Please paste a YouTube URL or article link to continue.");
      return;
    }
    if (inputMode === "pdf" && !pdfFile) {
      setError("Please select a PDF file to upload.");
      return;
    }
    if (!profileComplete) {
      setError("Please complete your profile (Settings -> enter a name) before generating.");
      return;
    }

    viewToken.current++;
    setError("");
    setLoading(true);
    setPost("");
    setActiveVersion(0);
    setGenerationIds([]);
    setEditing(false);

    try {
      let content: string;
      let sourceUrl: string | null = null;
      let sourceType: string | null = null;

      if (inputMode === "pdf" && pdfFile) {
        const formData = new FormData();
        formData.append("file", pdfFile);
        const scrapeRes = await apiFetch("/api/scrape/pdf-upload", {
          method: "POST", body: formData,
        });
        if (!scrapeRes.ok) {
          const errData = await scrapeRes.json().catch(() => null);
          throw new Error(errData?.detail || "Failed to extract text from the PDF.");
        }
        const scrapeData = await scrapeRes.json();
        content = scrapeData.content;
        sourceUrl = scrapeData.metadata?.filename || null;
        sourceType = "pdf";
      } else {
        const scrapeRes = await apiFetch("/api/scrape", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });
        if (!scrapeRes.ok) {
          const errData = await scrapeRes.json().catch(() => null);
          throw new Error(errData?.detail || "Failed to extract source content.");
        }
        const scrapeData = await scrapeRes.json();
        content = scrapeData.content;
        sourceUrl = url;
        sourceType = scrapeData.source_type;
      }

      const generateRes = await apiFetch("/api/generate/linkedin-post", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript: content,
          source_url: sourceUrl,
          source_type: sourceType,
          variants,
          ...(prompt ? { creative_direction: prompt } : {}),
        }),
      });

      if (!generateRes.ok) {
        const errData = await generateRes.json().catch(() => null);
        throw new Error(errData?.detail || "Failed to generate post.");
      }

      let streamError = "";
      let text = "";
      let saved = -1; // stays -1 until the done event arrives
      await readNdjson<GenerateEvent>(generateRes, (event) => {
        if (event.delta) {
          text += event.delta;
          setPost((prev) => prev + event.delta);
        } else if (event.error) streamError = event.error;
        else if (event.done) {
          saved = event.generation_ids?.length ?? 0;
          setGenerationIds(event.generation_ids ?? []);
          if (saved) setRefreshHistory((n) => n + 1);
        }
      });
      if (streamError) throw new Error(streamError);
      if (saved < 0) throw new Error("Generation was interrupted. Please retry.");
      // The backend keeps a single-version post whole, so only multi-version requests count tabs.
      const expected = variants > 1 ? splitVersions(text).length : Math.min(splitVersions(text).length, 1);
      if (saved === 0 && expected > 0) setError("Post generated but not saved to history.");
      else if (saved < expected) setError("Some versions weren't saved to history.");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "An unexpected error occurred.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleSettingsSaved = useCallback(() => {
    setProfileComplete(true);
  }, []);

  const handleLogout = async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // Backend failure does not block client-side logout
    } finally {
      router.replace("/login");
    }
  };

  if (!ready) {
    return <div className="min-h-screen flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-white/40" /></div>;
  }

  return (
    <main className="min-h-screen w-full relative flex flex-col items-center pt-20 pb-16 px-5 overflow-hidden">
      <div aria-hidden className="absolute top-[-15%] left-[-8%] w-[55%] h-[55%] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, oklch(0.55 0.22 255 / 0.13) 0%, transparent 70%)", filter: "blur(80px)" }}
      />
      <div aria-hidden className="absolute bottom-[-15%] right-[-8%] w-[45%] h-[50%] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, oklch(0.50 0.18 280 / 0.10) 0%, transparent 70%)", filter: "blur(80px)" }}
      />

      <header className="w-full max-w-4xl flex items-center justify-between mb-6 relative z-10">
        <div className="chip">
          <Zap className="w-3 h-3" />
          AI Content Engine
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setHistoryOpen(true)}
            title="History"
            className="p-2 rounded-xl bg-white/5 border border-white/10 text-white/40 hover:text-white/80 hover:bg-white/10 transition-all"
          >
            <Clock className="w-4 h-4" />
          </button>
          <button
            onClick={() => setSettingsOpen(true)}
            title="Settings"
            className="p-2 rounded-xl bg-white/5 border border-white/10 text-white/40 hover:text-white/80 hover:bg-white/10 transition-all"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      <header className="w-full max-w-4xl text-center space-y-5 mb-14 relative z-10">
        <h1
          className="text-[clamp(2.4rem,6vw,4.2rem)] font-semibold tracking-[-0.04em] text-white leading-[1.05]"
          style={{ letterSpacing: "-0.04em" }}
        >
          Source to{" "}
          <span className="inline-block"
            style={{
              background: "linear-gradient(135deg, oklch(0.72 0.18 255) 0%, oklch(0.65 0.22 280) 100%)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text",
            }}
          >
            LinkedIn Post
          </span>
        </h1>
        <p className="text-[15px] text-white/40 max-w-lg mx-auto font-light leading-relaxed tracking-[-0.01em]">
          Paste any YouTube URL or article link. Our AI distills the key insights into a premium, ready-to-publish post.
        </p>
      </header>

      <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-[2fr_3fr] gap-5 relative z-10">
        <GlassCard className="p-6 flex flex-col gap-6">
          <div className="flex gap-1.5 p-1 rounded-xl bg-white/[0.04] border border-white/[0.07]">
            <button
              id="mode-url"
              onClick={() => handleModeSwitch("url")}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 h-8 rounded-lg text-[12px] font-medium transition-all duration-200",
                inputMode === "url" ? "bg-white/10 text-white shadow-sm" : "text-white/35 hover:text-white/60"
              )}
            >
              <Link2 className="w-3.5 h-3.5" />
              URL / Link
            </button>
            <button
              id="mode-pdf"
              onClick={() => handleModeSwitch("pdf")}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 h-8 rounded-lg text-[12px] font-medium transition-all duration-200",
                inputMode === "pdf" ? "bg-white/10 text-white shadow-sm" : "text-white/35 hover:text-white/60"
              )}
            >
              <FileUp className="w-3.5 h-3.5" />
              Upload PDF
            </button>
          </div>

          {inputMode === "url" ? (
            <div className="flex flex-col gap-2.5">
              <Label>Source URL</Label>
              <div className="relative">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2">
                  <PlaySquare className="w-4 h-4 text-white/25" />
                </div>
                <input
                  id="source-url"
                  type="url"
                  placeholder="https://youtube.com/... or https://example.com/article"
                  className={cn(
                    "w-full h-11 pl-10 pr-4 rounded-xl text-[13.5px] font-light text-white placeholder-white/20",
                    "bg-white/5 border transition-all duration-200 outline-none",
                    "border-white/8 focus:border-white/20 focus:bg-white/8",
                    "focus:ring-2 focus:ring-[oklch(0.62_0.22_255_/_20%)]"
                  )}
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleGenerate()}
                />
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-2.5">
              <Label>PDF File</Label>
              <label
                id="pdf-upload-label"
                htmlFor="pdf-file-input"
                className={cn(
                  "flex flex-col items-center justify-center gap-2 w-full rounded-xl border-2 border-dashed transition-all duration-200 cursor-pointer select-none",
                  pdfFile
                    ? "border-[oklch(0.62_0.22_255_/_40%)] bg-[oklch(0.62_0.22_255_/_6%)]"
                    : "border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.05]",
                  "py-5"
                )}
              >
                {pdfFile ? (
                  <div className="flex items-center gap-2 px-4">
                    <FileUp className="w-4 h-4 text-[oklch(0.72_0.18_255)] shrink-0" />
                    <span className="text-[13px] text-white/80 font-light truncate max-w-[160px]">{pdfFile.name}</span>
                    <button type="button" onClick={(e) => { e.preventDefault(); setPdfFile(null); }}
                      className="ml-1 text-white/30 hover:text-white/60 transition-colors" title="Remove file"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <>
                    <FileUp className="w-5 h-5 text-white/20" />
                    <span className="text-[12.5px] text-white/30 font-light">
                      Click to browse or drop a <span className="text-white/50">.pdf</span> file
                    </span>
                  </>
                )}
              </label>
              <input id="pdf-file-input" type="file" accept=".pdf,application/pdf" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) setPdfFile(f); e.target.value = ""; }}
              />
            </div>
          )}

          <div className="flex flex-col gap-2.5 flex-1">
            <div className="flex items-center justify-between">
              <Label>Creative Direction</Label>
              <span className="text-[10px] text-white/20 font-normal">Optional</span>
            </div>
            <textarea
              id="prompt-override"
              placeholder="Leave blank for default tone, or guide the AI — e.g. &quot;Focus on the security angle. Keep it provocative.&quot;"
              className={cn(
                "flex-1 min-h-[130px] w-full p-3.5 rounded-xl text-[13px] font-light leading-relaxed",
                "text-white/80 placeholder-white/18 resize-none",
                "bg-white/5 border transition-all duration-200 outline-none",
                "border-white/8 focus:border-white/20 focus:bg-white/8",
                "focus:ring-2 focus:ring-[oklch(0.62_0.22_255_/_20%)]"
              )}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>

          <label className="flex items-center gap-2.5 text-[12.5px] text-white/50 font-light cursor-pointer select-none">
            <input
              id="variants-toggle"
              type="checkbox"
              checked={variants === 3}
              onChange={(e) => setVariants(e.target.checked ? 3 : 1)}
              className="w-3.5 h-3.5 accent-[oklch(0.62_0.22_255)]"
            />
            Write 3 versions with different hooks
          </label>

          {error && (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-red-500/8 border border-red-500/20">
              <span className="text-red-400 text-[13px] font-light leading-relaxed">{error}</span>
            </div>
          )}

          <button
            id="generate-btn"
            onClick={handleGenerate}
            disabled={loading || refining}
            className={cn(
              "w-full h-11 rounded-xl flex items-center justify-center gap-2",
              "text-[13.5px] font-semibold tracking-[-0.01em] transition-all duration-200",
              loading || refining
                ? "bg-white/8 text-white/30 cursor-not-allowed"
                : "bg-white text-[oklch(0.10_0.008_248)] hover:bg-white/92 active:scale-[0.98] glow-hover"
            )}
          >
            {loading ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Synthesizing post…</>
            ) : (
              <>Generate Post <ArrowRight className="w-4 h-4" /></>
            )}
          </button>
        </GlassCard>

        <GlassCard className="flex flex-col min-h-[460px]">
          <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-[oklch(0.72_0.18_255)]" />
              <Label className="!text-white/35">Generated Post</Label>
            </div>
            {shown && !loading && !editing && (
              <div className="flex items-center gap-2">
                {activeId && (
                  <button
                    onClick={() => { setDraft(shown); setEditing(true); }}
                    disabled={refining}
                    title="Edit post"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 text-white/50 border border-white/10 hover:bg-white/10 hover:text-white/80 disabled:opacity-50 transition-all duration-200"
                  >
                    <Pencil className="w-3.5 h-3.5" /> Edit
                  </button>
                )}
                <CopyButton text={shown} />
              </div>
            )}
          </div>

          {versions.length > 1 && (
            <div role="tablist" className="flex gap-1.5 px-6 pt-4">
              {versions.map((_, i) => (
                <button
                  key={i}
                  role="tab"
                  aria-selected={i === activeIndex}
                  onClick={() => { setActiveVersion(i); setEditing(false); }}
                  disabled={refining}
                  className={cn(
                    "h-7 px-3 rounded-lg text-[12px] font-medium transition-all duration-200",
                    i === activeIndex ? "bg-white/10 text-white" : "text-white/35 hover:text-white/60"
                  )}
                >
                  Version {i + 1}
                </button>
              ))}
            </div>
          )}

          <div className="flex-1 px-6 py-5 overflow-y-auto">
            {loading && !post ? (
              <div className="flex flex-col gap-3 pt-1">
                <SkeletonBlock className="h-3.5 w-2/3" />
                <SkeletonBlock className="h-3 w-5/6" />
                <SkeletonBlock className="h-3 w-4/5" />
                <div className="h-2" />
                <SkeletonBlock className="h-3 w-full" />
                <SkeletonBlock className="h-3 w-full" />
                <SkeletonBlock className="h-3 w-3/4" />
                <div className="h-2" />
                <SkeletonBlock className="h-3 w-full" />
                <SkeletonBlock className="h-3 w-5/6" />
                <SkeletonBlock className="h-3 w-1/2" />
                <div className="h-2" />
                <SkeletonBlock className="h-3 w-4/5" />
                <SkeletonBlock className="h-3 w-2/3" />
              </div>
            ) : editing ? (
              <div className="flex flex-col gap-3 h-full">
                <textarea
                  id="post-editor"
                  aria-label="Edit post"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  className="flex-1 min-h-[320px] w-full p-3.5 rounded-xl text-[13.5px] font-light leading-relaxed text-white/85 bg-white/5 border border-white/10 outline-none focus:border-white/20 resize-none"
                />
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => setEditing(false)}
                    className="h-8 px-3 rounded-lg text-[12px] text-white/50 border border-white/10 hover:bg-white/10 transition-all"
                  >Cancel</button>
                  <button
                    onClick={handleSaveEdit}
                    disabled={savingEdit || !draft.trim()}
                    className="h-8 px-3 rounded-lg text-[12px] font-semibold bg-white text-[oklch(0.10_0.008_248)] hover:bg-white/92 disabled:opacity-50 transition-all"
                  >{savingEdit ? "Saving…" : "Save"}</button>
                </div>
              </div>
            ) : shown ? (
              <div className="md-output">
                <ReactMarkdown>{shown}</ReactMarkdown>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full min-h-[300px] gap-4 select-none">
                <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
                  style={{ background: "oklch(0.62 0.22 255 / 8%)", border: "1px solid oklch(0.62 0.22 255 / 20%)" }}
                >
                  <Sparkles className="w-5 h-5 text-[oklch(0.65_0.18_255_/_60%)]" />
                </div>
                <div className="text-center">
                  <p className="text-[13px] text-white/25 font-light">
                    Paste a URL and hit <strong className="text-white/35 font-medium">Generate Post</strong>
                  </p>
                  <p className="text-[12px] text-white/15 mt-1">Supports public YouTube videos and articles</p>
                </div>
              </div>
            )}
          </div>

          {shown && activeId && !loading && !editing && (
            <div className="flex flex-wrap items-center gap-1.5 px-6 py-4 border-t border-white/[0.06]">
              {REFINE_PRESETS.map((preset) => (
                <button
                  key={preset}
                  onClick={() => handleRefine(preset)}
                  disabled={refining}
                  className="h-7 px-3 rounded-lg text-[12px] text-white/50 bg-white/5 border border-white/10 hover:bg-white/10 hover:text-white/80 disabled:opacity-50 transition-all"
                >{preset}</button>
              ))}
              <form
                className="flex-1 min-w-[160px]"
                onSubmit={(e) => { e.preventDefault(); if (refineText.trim()) handleRefine(refineText); }}
              >
                <input
                  aria-label="Custom refine instruction"
                  placeholder={refining ? "Refining…" : "Or tell the AI what to change, then Enter"}
                  value={refineText}
                  onChange={(e) => setRefineText(e.target.value)}
                  disabled={refining}
                  maxLength={1000}
                  className="w-full h-7 px-3 rounded-lg text-[12px] text-white/80 placeholder-white/20 bg-white/5 border border-white/10 outline-none focus:border-white/20 disabled:opacity-50"
                />
              </form>
            </div>
          )}
        </GlassCard>
      </div>

      <footer className="mt-14 text-center relative z-10">
        <p className="text-[11px] text-white/15 tracking-wide font-light">
          Powered by OpenRouter · LangSmith observability · FastAPI
        </p>
      </footer>

      <SettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} onSaved={handleSettingsSaved} onLogout={handleLogout} />
      <HistorySidebar
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        onSelect={(gen) => {
          if (refining) return;
          viewToken.current++;
          setPost(gen.generated_post);
          setActiveVersion(0);
          setGenerationIds([gen.id]);
          setEditing(false);
          if (gen.source_url) setUrl(gen.source_url);
        }}
        refreshKey={refreshHistory}
      />
    </main>
  );
}
