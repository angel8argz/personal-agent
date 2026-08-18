// Chat surface plus inline tool-confirmation approvals.
//
// HANDOFF.md left the confirmation UI pattern open; resolved as inline
// chat-style approval, so the pending command appears in the same stream the
// user is already reading rather than in a modal or a separate panel.
//
// The agent's run happens on a worker thread server-side, so this polls
// /chat/run for both the final answer and any confirmations waiting on a
// decision. Every approval shows the *literal* command, per HANDOFF.md.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchRun,
  resolveConfirmation,
  sendMessage,
  type PendingConfirmation,
} from "../api";

const POLL_INTERVAL_MS = 400;

interface Message {
  role: "you" | "tars" | "error";
  text: string;
}

function commandText(entry: PendingConfirmation): string {
  const command = entry.args?.command;
  return typeof command === "string" ? command : JSON.stringify(entry.args);
}

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [runId, setRunId] = useState<number | null>(null);
  const [pending, setPending] = useState<PendingConfirmation[]>([]);
  const [busy, setBusy] = useState(false);
  const streamRef = useRef<HTMLDivElement | null>(null);

  const append = useCallback((message: Message) => {
    setMessages((current) => [...current, message]);
  }, []);

  const finish = useCallback(() => {
    setRunId(null);
    setPending([]);
    setBusy(false);
  }, []);

  useEffect(() => {
    if (runId === null) return;
    let cancelled = false;

    async function poll() {
      try {
        const run = await fetchRun(runId as number);
        if (cancelled) return;
        setPending(run.pending);
        if (run.status === "done") {
          append({ role: "tars", text: run.answer ?? "" });
          finish();
        } else if (run.status === "error") {
          append({ role: "error", text: run.error ?? "the run failed" });
          finish();
        }
      } catch (e) {
        if (cancelled) return;
        append({ role: "error", text: (e as Error).message });
        finish();
      }
    }

    poll();
    const timer = window.setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [runId, append, finish]);

  const decide = useCallback(
    async (id: number, approved: boolean) => {
      setPending((current) => current.filter((entry) => entry.id !== id));
      try {
        await resolveConfirmation(id, approved);
      } catch (e) {
        append({ role: "error", text: (e as Error).message });
      }
    },
    [append]
  );

  // Single keypress to approve or deny, since Tier 2 confirmations will be
  // frequent. Ignored while the user is typing in the composer.
  useEffect(() => {
    if (pending.length === 0) return;
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      const key = event.key.toLowerCase();
      if (key !== "y" && key !== "n") return;
      event.preventDefault();
      void decide(pending[0].id, key === "y");
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pending, decide]);

  useEffect(() => {
    const stream = streamRef.current;
    if (stream) stream.scrollTop = stream.scrollHeight;
  }, [messages, pending]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    append({ role: "you", text });
    setDraft("");
    setBusy(true);
    try {
      const { run_id } = await sendMessage(text);
      setRunId(run_id);
    } catch (e) {
      append({ role: "error", text: (e as Error).message });
      setBusy(false);
    }
  }

  return (
    <section className="chat-panel">
      <header className="chat-header">
        <h2>Chat</h2>
        <span className="chat-status">
          {busy ? (pending.length > 0 ? "waiting on you" : "thinking") : "idle"}
        </span>
      </header>

      <div className="chat-stream" ref={streamRef}>
        {messages.length === 0 && pending.length === 0 && (
          <p className="chat-empty">
            Ask TARS something. Tool calls above Tier 1 will ask before running.
          </p>
        )}

        {messages.map((message, index) => (
          <div className={`chat-message chat-${message.role}`} key={index}>
            <span className="chat-role">{message.role}</span>
            <span className="chat-text">{message.text}</span>
          </div>
        ))}

        {pending.map((entry) => (
          <div className="approval" key={entry.id}>
            <div className="approval-head">
              <span className="approval-tier">tier {entry.tier}</span>
              <span className="approval-tool">{entry.tool}</span>
            </div>
            <code className="approval-command">{commandText(entry)}</code>
            <div className="approval-actions">
              <button type="button" onClick={() => void decide(entry.id, true)}>
                Approve <kbd>y</kbd>
              </button>
              <button
                type="button"
                className="approval-deny"
                onClick={() => void decide(entry.id, false)}
              >
                Deny <kbd>n</kbd>
              </button>
            </div>
          </div>
        ))}
      </div>

      <form className="chat-composer" onSubmit={submit}>
        <input
          type="text"
          value={draft}
          placeholder={busy ? "waiting for the current run..." : "Ask TARS..."}
          onChange={(event) => setDraft(event.target.value)}
          disabled={busy}
        />
        <button type="submit" disabled={busy || draft.trim() === ""}>
          Send
        </button>
      </form>
    </section>
  );
}
