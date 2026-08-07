import { useEffect, useRef, useState } from "react";
import { Bot, Send, Sparkles, User } from "lucide-react";
import { Card } from "@/components/ui/card";
import { useCoachAsk, useCoachStatus } from "@/hooks/queries";
import { cn } from "@/lib/utils";
import type { CoachMessage } from "@/lib/types";

type ChatMsg = CoachMessage & { mode?: "ai" | "local" };

const SUGGESTIONS = [
  "What should I focus on today?",
  "How are my streaks doing?",
  "How am I doing this week?",
  "How's my wellbeing?",
];

function Bubble({ msg, model }: { msg: ChatMsg; model?: string | null }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex gap-2.5", isUser ? "flex-row-reverse" : "flex-row")}>
      <span
        className={cn(
          "mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full",
          isUser ? "bg-ink/10 text-ink-muted" : "bg-accent-soft text-accent",
        )}
      >
        {isUser ? <User size={13} /> : <Bot size={13} />}
      </span>
      <div className={cn("min-w-0 max-w-[80%]", isUser ? "items-end text-right" : "items-start")}>
        <div
          className={cn(
            "inline-block whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm leading-relaxed",
            isUser ? "bg-accent text-white" : "glass-inset text-ink",
          )}
        >
          {msg.content}
        </div>
        {!isUser && msg.mode && (
          <div className="mt-1 px-1 text-[10px] text-ink-faint">
            Atlas · {msg.mode === "ai" ? `AI${model ? ` (${model})` : ""}` : "local"}
          </div>
        )}
      </div>
    </div>
  );
}

export function CoachPage() {
  const { data: status } = useCoachStatus();
  const ask = useCoachAsk();
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [useAi, setUseAi] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);

  const aiAvailable = status?.ai_available ?? false;
  const effectiveUseAi = useAi && aiAvailable;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, ask.isPending]);

  const send = (text: string) => {
    const q = text.trim();
    if (!q || ask.isPending) return;
    const next: ChatMsg[] = [...messages, { role: "user", content: q }];
    setMessages(next);
    setInput("");
    ask.mutate(
      { messages: next.map(({ role, content }) => ({ role, content })), useAi: effectiveUseAi },
      {
        onSuccess: (res) =>
          setMessages((m) => [...m, { role: "assistant", content: res.reply, mode: res.mode }]),
        onError: () =>
          setMessages((m) => [
            ...m,
            {
              role: "assistant",
              content: "I couldn't reach the coach just now — try again in a moment.",
              mode: "local",
            },
          ]),
      },
    );
  };

  return (
    <div className="animate-fade-in flex h-[calc(100vh-8rem)] flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-display font-semibold text-ink">Coach</h2>
          <p className="text-sm text-ink-muted">Grounded in your data. Ask anything.</p>
        </div>
        {aiAvailable ? (
          <button
            onClick={() => setUseAi((v) => !v)}
            className={cn(
              "flex items-center gap-2 rounded-full px-3 py-1.5 text-[12px] font-medium transition-colors",
              effectiveUseAi ? "bg-accent-soft text-accent" : "bg-ink/[0.06] text-ink-muted",
            )}
            title="Toggle the Claude-powered coach"
          >
            <Sparkles size={13} />
            {effectiveUseAi ? `AI on${status?.model ? ` · ${status.model}` : ""}` : "AI off"}
          </button>
        ) : (
          <span className="rounded-full bg-ink/[0.06] px-3 py-1.5 text-[12px] font-medium text-ink-muted">
            Local mode
          </span>
        )}
      </div>

      <Card className="flex min-h-0 flex-1 flex-col p-0">
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
              <span className="grid h-12 w-12 place-items-center rounded-2xl bg-accent-soft text-accent">
                <Bot size={22} />
              </span>
              <p className="max-w-xs text-sm text-ink-muted">
                I read your habits, streaks, wellbeing, and this week's review. Ask me for a read on
                your day, or try one of these:
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-full bg-ink/[0.06] px-3 py-1.5 text-[12px] text-ink-muted transition-colors hover:text-ink"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) => <Bubble key={i} msg={m} model={status?.model} />)
          )}
          {ask.isPending && (
            <div className="flex items-center gap-2.5 text-ink-faint">
              <span className="grid h-7 w-7 place-items-center rounded-full bg-accent-soft text-accent">
                <Bot size={13} />
              </span>
              <span className="text-sm">Thinking…</span>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="border-t border-border/10 p-3">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-center gap-2"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask your coach…"
              className="h-10 flex-1 rounded-xl bg-ink/[0.05] px-3.5 text-sm text-ink outline-none placeholder:text-ink-faint focus:bg-ink/[0.07]"
            />
            <button
              type="submit"
              disabled={!input.trim() || ask.isPending}
              aria-label="Send"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent text-white transition-opacity disabled:opacity-40"
            >
              <Send size={16} />
            </button>
          </form>
          <p className="mt-1.5 px-1 text-[10px] text-ink-faint">
            {effectiveUseAi
              ? "AI mode sends a short summary of your data to Anthropic."
              : aiAvailable
                ? "Local mode — answered on your device from your data."
                : "Running locally on your device. Set ATLAS_ANTHROPIC_API_KEY to enable the Claude coach (which sends your data to Anthropic)."}
          </p>
        </div>
      </Card>
    </div>
  );
}
