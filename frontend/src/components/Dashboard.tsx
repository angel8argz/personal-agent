// Dashboard wired to the local TARS agent HTTP server (agent/server.py) per
// IMPLEMENTATION.md "Decision - Step 3 transport".
//
// Registering a project root here is what grants the Tier 1/2 tools access to
// a directory (see agent/tools/scoping.py) — before this form existed, that
// was only possible from a Python REPL.

import { useCallback, useEffect, useState } from "react";
import {
  createProject,
  fetchProjects,
  fetchUpcomingTasks,
  type Project,
  type Task,
} from "../api";

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

  const [name, setName] = useState("");
  const [rootPath, setRootPath] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [projectsData, tasksData] = await Promise.all([
        fetchProjects(),
        fetchUpcomingTasks(7),
      ]);
      setProjects(projectsData);
      setTasks(tasksData);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function addProject(event: React.FormEvent) {
    event.preventDefault();
    if (saving || name.trim() === "") return;
    setSaving(true);
    setFormError(null);
    try {
      await createProject(name.trim(), rootPath.trim());
      setName("");
      setRootPath("");
      await load();
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

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

      <form className="add-project" onSubmit={addProject}>
        <input
          type="text"
          value={name}
          placeholder="Project name"
          onChange={(event) => setName(event.target.value)}
        />
        <input
          type="text"
          value={rootPath}
          placeholder="Directory to grant access to (optional)"
          onChange={(event) => setRootPath(event.target.value)}
        />
        <button type="submit" disabled={saving || name.trim() === ""}>
          Add project
        </button>
      </form>
      {formError && <p className="form-error">{formError}</p>}

      {projects.length === 0 ? (
        <p className="subtitle">
          No projects yet. Add one above — TARS can't touch any directory until
          it's registered here.
        </p>
      ) : (
        <div className="project-columns">
          {projects.map((project) => {
            const projectTasks = tasks.filter((task) => task.project_id === project.id);
            return (
              <section className="project-column" key={project.id}>
                <h2>{project.name}</h2>
                {project.root_path && <p className="project-root">{project.root_path}</p>}
                {projectTasks.length === 0 ? (
                  <p className="project-empty">Nothing due this week.</p>
                ) : (
                  <ul className="task-list">
                    {projectTasks.map((task) => (
                      <li className={`task task-${task.status}`} key={task.id}>
                        <span className="task-title">{task.title}</span>
                        <span className="task-meta">
                          <span className={`status-pill status-${task.status}`}>
                            {statusLabel(task.status)}
                          </span>
                          {task.due_date && <span className="task-due">Due {task.due_date}</span>}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
