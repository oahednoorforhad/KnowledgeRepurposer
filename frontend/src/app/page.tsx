"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  Sparkles,
  ArrowRight,
  Loader2,
  PlaySquare,
  Copy,
  Check,
  Zap,
  FileUp,
  Link2,
  X,
} from "lucide-react";

// ── tiny utility ──────────────────────────────────────
function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(" ");
}

// ── reusable primitives ───────────────────────────────
function Label({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cn("label-caps", className)}>{children}</p>;
}

function GlassCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("glass rounded-2xl", className)}>{children}</div>
  );
}

// ── Copy-to-clipboard button ──────────────────────────
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
      {copied ? (
        <><Check className="w-3.5 h-3.5" /> Copied</>
      ) : (
        <><Copy className="w-3.5 h-3.5" /> Copy</>
      )}
    </button>
  );
}

// ── Skeleton pulse ─────────────────────────────────────
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

// ── Main Page ─────────────────────────────────────────
export default function Home() {
  const [inputMode, setInputMode] = useState<"url" | "pdf">("url");
  const [url, setUrl] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [post, setPost] = useState("");
  const [error, setError] = useState("");

  const handleModeSwitch = (mode: "url" | "pdf") => {
    setInputMode(mode);
    setError("");
    setUrl("");
    setPdfFile(null);
  };

  const handleGenerate = async () => {
    if (inputMode === "url" && !url) {
      setError("Please paste a YouTube URL or article link to continue.");
      return;
    }
    if (inputMode === "pdf" && !pdfFile) {
      setError("Please select a PDF file to upload.");
      return;
    }

    setError("");
    setLoading(true);
    setPost("");

    try {
      let content: string;

      if (inputMode === "pdf" && pdfFile) {
        const formData = new FormData();
        formData.append("file", pdfFile);
        const scrapeRes = await fetch("http://127.0.0.1:8000/api/scrape/pdf-upload", {
          method: "POST",
          body: formData,
        });
        if (!scrapeRes.ok) {
          const errData = await scrapeRes.json().catch(() => null);
          throw new Error(errData?.detail || "Failed to extract text from the PDF.");
        }
        ({ content } = await scrapeRes.json());
      } else {
        const scrapeRes = await fetch("http://127.0.0.1:8000/api/scrape", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });
        if (!scrapeRes.ok) {
          const errData = await scrapeRes.json().catch(() => null);
          throw new Error(errData?.detail || "Failed to extract source content.");
        }
        ({ content } = await scrapeRes.json());
      }

      const generateRes = await fetch("http://127.0.0.1:8000/api/generate/linkedin-post", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript: content,
          ...(prompt ? { creative_direction: prompt } : {}),
        }),
      });

      if (!generateRes.ok) {
        const errData = await generateRes.json().catch(() => null);
        throw new Error(errData?.detail || "Failed to generate post.");
      }

      const data = await generateRes.json();
      setPost(data.post);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "An unexpected error occurred.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen w-full relative flex flex-col items-center pt-20 pb-16 px-5 overflow-hidden">

      {/* ── Ambient orbs ───────────────────────────────── */}
      <div
        aria-hidden
        className="absolute top-[-15%] left-[-8%] w-[55%] h-[55%] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, oklch(0.55 0.22 255 / 0.13) 0%, transparent 70%)", filter: "blur(80px)" }}
      />
      <div
        aria-hidden
        className="absolute bottom-[-15%] right-[-8%] w-[45%] h-[50%] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, oklch(0.50 0.18 280 / 0.10) 0%, transparent 70%)", filter: "blur(80px)" }}
      />

      {/* ── Hero ───────────────────────────────────────── */}
      <header className="w-full max-w-4xl text-center space-y-5 mb-14 relative z-10">
        <div className="chip mx-auto w-fit mb-2">
          <Zap className="w-3 h-3" />
          AI Content Engine
        </div>

        <h1
          className="text-[clamp(2.4rem,6vw,4.2rem)] font-semibold tracking-[-0.04em] text-white leading-[1.05]"
          style={{ letterSpacing: "-0.04em" }}
        >
          Source to{" "}
          <span
            className="inline-block"
            style={{
              background: "linear-gradient(135deg, oklch(0.72 0.18 255) 0%, oklch(0.65 0.22 280) 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            LinkedIn Post
          </span>
        </h1>

        <p className="text-[15px] text-white/40 max-w-lg mx-auto font-light leading-relaxed tracking-[-0.01em]">
          Paste any YouTube URL or article link. Our AI distills the key insights into a premium, ready-to-publish post.
        </p>
      </header>

      {/* ── Main grid ──────────────────────────────────── */}
      <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-[2fr_3fr] gap-5 relative z-10">

        {/* ── Input panel ─────────────────────────────── */}
        <GlassCard className="p-6 flex flex-col gap-6">

          {/* Input mode toggle */}
          <div className="flex gap-1.5 p-1 rounded-xl bg-white/[0.04] border border-white/[0.07]">
            <button
              id="mode-url"
              onClick={() => handleModeSwitch("url")}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 h-8 rounded-lg text-[12px] font-medium transition-all duration-200",
                inputMode === "url"
                  ? "bg-white/10 text-white shadow-sm"
                  : "text-white/35 hover:text-white/60"
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
                inputMode === "pdf"
                  ? "bg-white/10 text-white shadow-sm"
                  : "text-white/35 hover:text-white/60"
              )}
            >
              <FileUp className="w-3.5 h-3.5" />
              Upload PDF
            </button>
          </div>

          {/* Source input */}
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
                  "flex flex-col items-center justify-center gap-2 w-full rounded-xl border-2 border-dashed",
                  "transition-all duration-200 cursor-pointer select-none",
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
                    <button
                      type="button"
                      onClick={(e) => { e.preventDefault(); setPdfFile(null); }}
                      className="ml-1 text-white/30 hover:text-white/60 transition-colors"
                      title="Remove file"
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
              <input
                id="pdf-file-input"
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) setPdfFile(f);
                  e.target.value = "";
                }}
              />
            </div>
          )}

          {/* Prompt override */}
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

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-red-500/8 border border-red-500/20">
              <span className="text-red-400 text-[13px] font-light leading-relaxed">{error}</span>
            </div>
          )}

          {/* Generate button */}
          <button
            id="generate-btn"
            onClick={handleGenerate}
            disabled={loading}
            className={cn(
              "w-full h-11 rounded-xl flex items-center justify-center gap-2",
              "text-[13.5px] font-semibold tracking-[-0.01em] transition-all duration-200",
              loading
                ? "bg-white/8 text-white/30 cursor-not-allowed"
                : "bg-white text-[oklch(0.10_0.008_248)] hover:bg-white/92 active:scale-[0.98] glow-hover"
            )}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Synthesizing post…
              </>
            ) : (
              <>
                Generate Post
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </GlassCard>

        {/* ── Output panel ────────────────────────────── */}
        <GlassCard className="flex flex-col min-h-[460px]">
          {/* Panel header */}
          <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-[oklch(0.72_0.18_255)]" />
              <Label className="!text-white/35">Generated Post</Label>
            </div>
            {post && <CopyButton text={post} />}
          </div>

          {/* Panel body */}
          <div className="flex-1 px-6 py-5 overflow-y-auto">
            {loading ? (
              /* Skeleton */
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
            ) : post ? (
              /* Markdown output */
              <div className="md-output">
                <ReactMarkdown>{post}</ReactMarkdown>
              </div>
            ) : (
              /* Empty state */
              <div className="flex flex-col items-center justify-center h-full min-h-[300px] gap-4 select-none">
                <div
                  className="w-12 h-12 rounded-2xl flex items-center justify-center"
                  style={{
                    background: "oklch(0.62 0.22 255 / 8%)",
                    border: "1px solid oklch(0.62 0.22 255 / 20%)",
                  }}
                >
                  <Sparkles className="w-5 h-5 text-[oklch(0.65_0.18_255_/_60%)]" />
                </div>
                <div className="text-center">
                  <p className="text-[13px] text-white/25 font-light">
                    Paste a URL and hit <strong className="text-white/35 font-medium">Generate Post</strong>
                  </p>
                  <p className="text-[12px] text-white/15 mt-1">
                    Supports public YouTube videos and articles
                  </p>
                </div>
              </div>
            )}
          </div>
        </GlassCard>
      </div>

      {/* ── Footer ─────────────────────────────────────── */}
      <footer className="mt-14 text-center relative z-10">
        <p className="text-[11px] text-white/15 tracking-wide font-light">
          Powered by OpenRouter · LangSmith observability · FastAPI
        </p>
      </footer>

    </main>
  );
}
