"use client";

import { useRef, useState } from "react";
import { apiPost } from "@/lib/api";
import { escapeHtml } from "@/lib/report";
import ReportBar from "@/components/ReportBar";

interface Msg {
  role: "user" | "assistant";
  content: string;
}

export default function ChatTool() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  async function send() {
    const content = input.trim();
    if (!content || loading) return;
    const next = [...messages, { role: "user" as const, content }];
    setMessages(next);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const d = await apiPost<{ reply: string }>("/tools/chat", { messages: next });
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
      <div className="min-h-[320px] space-y-3 rounded-xl border border-c surface-2 p-4">
        {messages.length === 0 && (
          <p className="text-sm text-neutral-400">
            Mulai percakapan — minta bantuan menulis, merangkum, atau menjelaskan materi akademik.
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
        {loading && <div className="text-sm text-neutral-400">Mengetik…</div>}
        <div ref={endRef} />
      </div>
      {messages.length > 0 && (
        <ReportBar
          source={messages.map((m) => `${m.role}: ${m.content}`).join("\n")}
          title="Transkrip Percakapan AI Chat"
          filename="transkrip-ai-chat"
          disclaimer="Transkrip percakapan dengan asisten AI sebagai arsip bahan bantu; tinjau kembali setiap jawaban sebelum digunakan. ID Laporan & hash bersifat reproducible sehingga laporan dapat diverifikasi."
          buildBody={() =>
            `<h2>Percakapan</h2>${messages
              .map(
                (m) =>
                  `<div style="margin:10px 0"><b>${
                    m.role === "user" ? "Pengguna" : "Asisten"
                  }</b><br><div class="doc">${escapeHtml(m.content)}</div></div>`,
              )
              .join("")}`
          }
        />
      )}
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
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
          placeholder="Tulis pesan… (Enter untuk kirim)"
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
    </div>
  );
}
