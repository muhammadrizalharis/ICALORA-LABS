"use client";

import { useRef, useState } from "react";
import { apiPost, apiUpload } from "@/lib/api";
import { escapeHtml } from "@/lib/report";
import ReportBar from "@/components/ReportBar";

interface Msg {
  role: "user" | "assistant";
  content: string;
}
interface ExtractResult {
  filename: string;
  text: string;
  chars: number;
}

const ACCEPT = ".txt,.md,.csv,.tex,.pdf,.docx";

export default function ChatPdfTool() {
  const [context, setContext] = useState("");
  const [docName, setDocName] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  async function handleFile(file: File) {
    setError(null);
    setUploading(true);
    setMessages([]);
    try {
      const res = await apiUpload<ExtractResult>("/tools/extract-text", file);
      setContext(res.text);
      setDocName(`${res.filename} · ${res.chars.toLocaleString("id-ID")} karakter`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal membaca berkas.");
    } finally {
      setUploading(false);
    }
  }

  async function send() {
    const content = input.trim();
    if (!content || loading || !context) return;
    const next = [...messages, { role: "user" as const, content }];
    setMessages(next);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const d = await apiPost<{ reply: string }>("/tools/doc-chat", { context, messages: next });
      setMessages([...next, { role: "assistant", content: d.reply }]);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div
        onClick={() => fileRef.current?.click()}
        className="cursor-pointer rounded-xl border border-dashed border-c surface-2 p-6 text-center transition hover:border-[color:var(--brand)]"
      >
        <input
          ref={fileRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {uploading ? (
          <span className="text-sm text-neutral-400">Mengekstrak dokumen…</span>
        ) : docName ? (
          <span className="text-sm text-emerald-600 dark:text-emerald-400">📄 {docName}</span>
        ) : (
          <span className="text-sm text-neutral-500 dark:text-neutral-400">
            Klik untuk unggah PDF / DOCX / TXT, lalu ajukan pertanyaan tentang isinya.
          </span>
        )}
      </div>

      {context && (
        <>
          <div className="min-h-[260px] space-y-3 rounded-xl border border-c surface-2 p-4">
            {messages.length === 0 && (
              <p className="text-sm text-neutral-400">
                Dokumen siap. Tanyakan apa saja — jawaban hanya diambil dari isi dokumen.
              </p>
            )}
            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
                <div
                  className={
                    "inline-block max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm " +
                    (m.role === "user"
                      ? "bg-[color:var(--brand)] text-white"
                      : "surface border border-c text-neutral-900 dark:text-neutral-100")
                  }
                >
                  {m.content}
                </div>
              </div>
            ))}
            {loading && <div className="text-sm text-neutral-400">Membaca dokumen…</div>}
            <div ref={endRef} />
          </div>
          {messages.length > 0 && (
            <ReportBar
              source={(docName ?? "") + "\n" + messages.map((m) => `${m.role}: ${m.content}`).join("\n")}
              title="Transkrip Tanya-Jawab Dokumen (Chat PDF)"
              filename="transkrip-chat-pdf"
              disclaimer="Transkrip tanya-jawab berdasarkan dokumen yang diunggah sebagai arsip bahan bantu; jawaban mengacu pada isi dokumen dan sebaiknya diverifikasi. ID Laporan & hash bersifat reproducible sehingga laporan dapat diverifikasi."
              buildBody={() =>
                `${docName ? `<p class="muted">Dokumen: ${escapeHtml(docName)}</p>` : ""}` +
                `<h2>Percakapan</h2>${messages
                  .map(
                    (m) =>
                      `<div style="margin:10px 0"><b>${
                        m.role === "user" ? "Pertanyaan" : "Jawaban"
                      }</b><br><div class="doc">${escapeHtml(m.content)}</div></div>`,
                  )
                  .join("")}`
              }
            />
          )}
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={2}
              placeholder="Tanya tentang dokumen… (Enter untuk kirim)"
              className="flex-1 resize-none rounded-lg border border-c surface px-3 py-2 text-sm focus:border-[color:var(--brand)] focus:outline-none"
            />
            <button
              onClick={send}
              disabled={loading || !input.trim()}
              className="rounded-lg bg-[color:var(--brand)] px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
            >
              Kirim
            </button>
          </div>
        </>
      )}
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}
    </div>
  );
}
