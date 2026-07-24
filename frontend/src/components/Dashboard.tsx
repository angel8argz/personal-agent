// Dashboard wired to the local TARS agent HTTP server (agent/server.py) per
// IMPLEMENTATION.md "Decision - Step 3 transport". Reads only; writes stay a
// future step per ARCHITECTURE.md's steady-state data flow.

import { useEffect, useState } from "react";

const AGENT_BASE = "http://127.0.0.1:8765";

interface Project {
  id: number;
  name: string;
  description?: string | null;
  root_path?: string | null;
  created_at?: string;
}

interface Task {
  id: number;
  project_id: number;
  title: string;
  notes?: string | null;
  status: string;
  due_date: string | null;
  created_at?: string;
  completed_at?: string | null;
}

function statusLabel(status: string): string {
  if (status === "done") return "Done";
  if (status === "in_progress") return "In progress";
  return "To do";
}

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [projectsRes, tasksRes] = await Promise.all([
          fetch(`${AGENT_BASE}/projects`),
          fetch(`${AGENT_BASE}/tasks/upcoming?within_days=7`),
        ]);
        if (!projectsRes.ok || !tasksRes.ok) {
          throw new Error("agent responded with an error status");
        }
        const projectsData: Project[] = await projectsRes.json();
        const tasksData: Task[] = await tasksRes.json();
        if (!cancelled) {
          setProjects(projectsData);
          setTasks(tasksData);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setError(true);
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="dashboard">
        <header className="dashboard-header">
          <h1>TARS</h1>
          <p className="subtitle">Loading...</p>
        </header>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard">
        <header className="dashboard-header">
          <h1>TARS</h1>
          <p className="subtitle">
            Can't reach the TARS agent — is `python3 agent/server.py` running?
          </p>
        </header>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>TARS</h1>
        <p className="subtitle">Local agent</p>
      </header>

      <div className="project-columns">
        {projects.map((project) => (
          <section className="project-column" key={project.id}>
            <h2>{project.name}</h2>
            <ul className="task-list">
              {tasks
                .filter((task) => task.project_id === project.id)
                .map((task) => (
                  <li className={`task task-${task.status}`} key={task.id}>
                    <span className="task-title">{task.title}</span>
                    <span className="task-meta">
                      <span className={`status-pill status-${task.status}`}>
                        {statusLabel(task.status)}
                      </span>
                      {task.due_date && (
                        <span className="task-due">Due {task.due_date}</span>
                      )}
                    </span>
                  </li>
                ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
