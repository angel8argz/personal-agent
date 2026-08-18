// Client for the local TARS agent HTTP server (agent/server.py).
// The server checks Origin, so these requests only work from the vite dev
// server or the packaged webview — see ALLOWED_ORIGINS there.

// Override with VITE_AGENT_BASE when 8765 is taken (the port is not reserved,
// and TARS_PORT moves the server side to match).
const AGENT_BASE = import.meta.env.VITE_AGENT_BASE ?? "http://127.0.0.1:8765";

export interface Project {
  id: number;
  name: string;
  description?: string | null;
  root_path?: string | null;
  created_at?: string;
}

export interface Task {
  id: number;
  project_id: number;
  title: string;
  notes?: string | null;
  status: string;
  due_date: string | null;
  created_at?: string;
  completed_at?: string | null;
}

export interface PendingConfirmation {
  id: number;
  tool: string;
  tier: number;
  args: Record<string, unknown>;
}

export interface RunStatus {
  status: "running" | "done" | "error";
  answer: string | null;
  error: string | null;
  pending: PendingConfirmation[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${AGENT_BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.error) detail = body.error;
    } catch {
      // non-JSON error body; the status text will do
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

function jsonPost(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export const fetchProjects = () => request<Project[]>("/projects");

export const fetchUpcomingTasks = (withinDays = 7) =>
  request<Task[]>(`/tasks/upcoming?within_days=${withinDays}`);

export const createProject = (name: string, rootPath: string) =>
  request<{ id: number }>("/projects", jsonPost({ name, root_path: rootPath }));

export const sendMessage = (message: string) =>
  request<{ run_id: number }>("/chat", jsonPost({ message }));

export const fetchRun = (runId: number) => request<RunStatus>(`/chat/run?id=${runId}`);

export const resolveConfirmation = (id: number, approved: boolean) =>
  request<{ resolved: boolean }>("/chat/confirm", jsonPost({ id, approved }));
