import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Copy,
  ExternalLink,
  Link2,
  LogOut,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import Brand from "./components/Brand";
import Modal from "./components/Modal";
import LinkForm from "./components/LinkForm";
import StatsDialog from "./components/StatsDialog";
import { api, ApiError, shortUrl } from "./api";
import type { Link, LinkPage, User } from "./api";
import { errorMessage, number } from "./utils";

export default function Dashboard({
  user,
  loggedOut,
}: {
  user: User;
  loggedOut: () => void;
}) {
  const [page, setPage] = useState<LinkPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editor, setEditor] = useState<Link | "new" | null>(null);
  const [stats, setStats] = useState<Link | null>(null);
  const [deleting, setDeleting] = useState<Link | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const closeEditor = useCallback(() => setEditor(null), []);
  const closeStats = useCallback(() => setStats(null), []);
  const closeDelete = useCallback(() => setDeleting(null), []);
  const refresh = useCallback(async () => {
    try {
      setPage(await api<LinkPage>(`/links?limit=20&offset=${offset}`));
      setError("");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) loggedOut();
      else setError(errorMessage(e));
    }
  }, [offset, loggedOut]);
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 3500);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    if (page && offset > 0 && page.items.length === 0)
      setOffset(Math.max(0, offset - 20));
  }, [page, offset]);
  async function copy(link: Link) {
    try {
      await navigator.clipboard.writeText(shortUrl(link.code));
      setNotice("Link copied. Ready to share!");
    } catch {
      setError(
        `Could not copy automatically. Your link: ${shortUrl(link.code)}`,
      );
    }
  }
  async function toggle(link: Link) {
    setBusy(link.id);
    try {
      await api(`/links/${link.id}`, "PATCH", { enabled: !link.enabled });
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }
  async function remove() {
    if (!deleting) return;
    setBusy(deleting.id);
    try {
      await api(`/links/${deleting.id}`, "DELETE");
      setDeleting(null);
      setNotice("Link deleted.");
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }
  async function logout() {
    try {
      await api("/auth/logout", "POST");
      loggedOut();
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  const filtered =
    page?.items.filter((link) =>
      `${link.name} ${link.target_url} ${link.code}`
        .toLowerCase()
        .includes(query.toLowerCase()),
    ) || [];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <div className="workspace-label">YOUR WORKSPACE</div>
        <a href="/dashboard" className="nav-item active">
          <Link2 size={19} /> My links <span>{page?.total || 0}</span>
        </a>
        <div className="sidebar-note">
          <span className="note-icon">
            <Activity size={20} />
          </span>
          <h3>Good things, neatly shared.</h3>
          <p>Every little link is a chance to connect.</p>
          <div className="note-decoration">
            <span />
            <span />
            <span />
            <span />
            <span />
          </div>
        </div>
        <div className="profile">
          <span className="avatar">{user.email[0].toUpperCase()}</span>
          <div>
            <strong>Your account</strong>
            <span title={user.email}>{user.email}</span>
          </div>
          <button className="icon-btn" onClick={logout} aria-label="Sign out">
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <span>
            Workspace <span className="crumb">/</span> <strong>My links</strong>
          </span>
          <span className="topbar-tag">
            <span /> Personal workspace
          </span>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">MAKE EVERY CONNECTION COUNT</span>
              <h1>
                Small links. Big possibilities<span>.</span>
              </h1>
              <p>
                A little less URL. A lot more possibility. All your links, in
                one place.
              </p>
            </div>
            <button
              className="btn btn-brand create-button"
              onClick={() => setEditor("new")}
            >
              <Plus size={19} /> Create a link
            </button>
          </div>
          {error && (
            <div
              role="alert"
              className="alert alert-danger d-flex align-items-center justify-content-between gap-3"
            >
              <span>{error}</span>
              <button
                className="btn btn-sm btn-outline-danger"
                onClick={() => void refresh()}
              >
                Try again
              </button>
            </div>
          )}
          <section className="summary-grid" aria-label="Overview">
            <Summary
              label="Total links"
              value={page?.total}
              icon={<Link2 size={20} />}
              foot="All your connections in one place"
            />
            <Summary
              label="Total clicks"
              value={page?.total_clicks}
              icon={<BarChart3 size={20} />}
              foot="Every visit tells a little story"
            />
            <Summary
              label="Active links"
              value={page?.active}
              icon={<Activity size={20} />}
              foot="Out there, ready to be discovered"
            />
          </section>
          <section className="links-section">
            <div className="section-toolbar">
              <div>
                <h2>
                  My links <span>{page?.total || 0}</span>
                </h2>
                <p>Your shortcuts to something good.</p>
              </div>
              <div className="search-field">
                <Search size={18} />
                <input
                  aria-label="Search links on this page"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search this page…"
                />
              </div>
            </div>
            <div className="table-responsive">
              <table className="links-table">
                <thead>
                  <tr>
                    <th>NAME / DESTINATION</th>
                    <th>SHORT LINK</th>
                    <th>CLICKS</th>
                    <th>STATUS</th>
                    <th>
                      <span className="visually-hidden">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((link) => (
                    <tr key={link.id}>
                      <td>
                        <div className="link-info">
                          <span className="link-tile">
                            <Link2 size={22} />
                          </span>
                          <div>
                            <strong>{link.name}</strong>
                            <a
                              className="target-url"
                              href={link.target_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              title={link.target_url}
                            >
                              {link.target_url}
                            </a>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="short-link">
                          <a
                            href={`/r/${link.code}`}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            /r/{link.code}
                            <ExternalLink size={13} />
                          </a>
                          <button
                            className="icon-btn"
                            onClick={() => void copy(link)}
                            aria-label={`Copy ${link.name}`}
                          >
                            <Copy size={16} />
                          </button>
                        </div>
                      </td>
                      <td>
                        <button
                          className="click-count"
                          onClick={() => setStats(link)}
                          aria-label={`Stats for ${link.name}`}
                        >
                          <BarChart3 size={15} />
                          {number.format(link.total_clicks)}
                        </button>
                      </td>
                      <td>
                        <button
                          className={`status-badge ${link.enabled ? "enabled" : "disabled"}`}
                          disabled={busy === link.id}
                          onClick={() => void toggle(link)}
                          title="Click to enable or disable"
                          aria-label={`${link.enabled ? "Disable" : "Enable"} ${link.name}`}
                        >
                          <span />
                          {link.enabled ? "Active" : "Paused"}
                        </button>
                      </td>
                      <td>
                        <div className="row-actions">
                          <button
                            className="icon-btn"
                            onClick={() => setEditor(link)}
                            aria-label={`Edit ${link.name}`}
                          >
                            <Pencil size={16} />
                          </button>
                          <button
                            className="icon-btn delete-btn"
                            onClick={() => setDeleting(link)}
                            aria-label={`Delete ${link.name}`}
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!page && !error && (
              <div className="empty-state" role="status">
                Gathering your connections…
              </div>
            )}
            {page && filtered.length === 0 && (
              <div className="empty-state">
                <span className="empty-icon">
                  <Link2 size={30} />
                </span>
                <h3>
                  {query
                    ? "No matching links just yet"
                    : "Your first connection starts here"}
                </h3>
                <p>
                  {query
                    ? "Try another name, code, or destination on this page."
                    : "Turn a long address into something short, sweet, and ready to share."}
                </p>
                {!query && (
                  <button
                    className="btn btn-brand"
                    onClick={() => setEditor("new")}
                  >
                    <Plus size={18} /> Create your first link
                  </button>
                )}
              </div>
            )}
            {page && (
              <div className="table-footer">
                <span>
                  {page.total
                    ? `${offset + 1}–${Math.min(offset + 20, page.total)} of ${page.total} links`
                    : "No links yet"}
                  {query && ` · ${filtered.length} matches on this page`}
                </span>
                <div>
                  <button
                    className="icon-btn"
                    aria-label="Previous page"
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - 20))}
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <span>{Math.floor(offset / 20) + 1}</span>
                  <button
                    className="icon-btn"
                    aria-label="Next page"
                    disabled={offset + 20 >= page.total}
                    onClick={() => setOffset(offset + 20)}
                  >
                    <ChevronRight size={18} />
                  </button>
                </div>
              </div>
            )}
          </section>
          <footer className="page-footer">
            <span>Less URL. More possibility.</span>
            <span>
              Made for your next connection <Link2 size={14} />
            </span>
          </footer>
        </div>
      </main>
      {notice && (
        <div className="toast-message" role="status">
          <CheckCircle2 size={20} />
          {notice}
        </div>
      )}
      {editor && (
        <LinkForm
          link={editor === "new" ? undefined : editor}
          close={closeEditor}
          saved={() => {
            setEditor(null);
            setNotice(
              editor === "new" ? "Your new link is ready!" : "Changes saved.",
            );
            void refresh();
          }}
        />
      )}
      {stats && <StatsDialog link={stats} close={closeStats} />}
      {deleting && (
        <Modal title="Delete this link?" close={closeDelete}>
          <p>
            Link <strong>{deleting.name}</strong> and its stats will be deleted.
            The short link will stop working.
          </p>
          <div className="dialog-actions">
            <button className="btn btn-light" onClick={closeDelete}>
              Keep link
            </button>
            <button
              className="btn btn-danger"
              disabled={busy === deleting.id}
              onClick={() => void remove()}
            >
              {busy ? "Deleting…" : "Delete link"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Summary({
  label,
  value,
  icon,
  foot,
}: {
  label: string;
  value?: number;
  icon: ReactNode;
  foot: string;
}) {
  return (
    <div className="summary-card">
      <div className="summary-top">
        <span>{label}</span>
        <span className="summary-icon">{icon}</span>
      </div>
      <strong className="summary-value">
        {value === undefined ? "—" : number.format(value)}
      </strong>
      <p>{foot}</p>
    </div>
  );
}
