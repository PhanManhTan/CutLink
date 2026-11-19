import { useCallback, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Link2,
  LogOut,
  Plus,
  Search,
  RefreshCw,
} from "lucide-react";
import Brand from "./components/Brand";
import Modal from "./components/Modal";
import LinkForm from "./components/LinkForm";
import StatsDialog from "./components/StatsDialog";
import { api } from "./api";
import type { Link, User } from "./api";
import { errorMessage, number } from "./utils";
import { useLinks } from "./useLinks";
import LinkTable from "./components/LinkTable";

export default function Dashboard({
  user,
  loggedOut,
}: {
  user: User;
  loggedOut: () => void;
}) {
  const {
    page,
    offset,
    setOffset,
    error,
    setError,
    notice,
    setNotice,
    busy,
    refresh,
    copy,
    toggle,
    remove,
  } = useLinks(loggedOut);
  const [query, setQuery] = useState("");
  const [editor, setEditor] = useState<Link | "new" | null>(null);
  const [stats, setStats] = useState<Link | null>(null);
  const [deleting, setDeleting] = useState<Link | null>(null);
  const closeEditor = useCallback(() => setEditor(null), []);
  const closeStats = useCallback(() => setStats(null), []);
  const closeDelete = useCallback(() => setDeleting(null), []);
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
          <h3>Your links, under control.</h3>
          <p>Choose a custom ending, share your link, and track its clicks.</p>
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
              <span className="eyebrow">SHORTEN. SHARE. TRACK.</span>
              <h1>
                Cut the long link<span>.</span>
              </h1>
              <p>
                Create short links, choose custom endings, and track click
                activity in one place.
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
              foot="Links in your account"
            />
            <Summary
              label="Total clicks"
              value={page?.total_clicks}
              icon={<BarChart3 size={20} />}
              foot="Recorded visits across your links"
            />
            <Summary
              label="Active links"
              value={page?.active}
              icon={<Activity size={20} />}
              foot="Ready to redirect visitors"
            />
          </section>
          <section className="links-section">
            <div className="section-toolbar">
              <div>
                <h2>
                  My links <span>{page?.total || 0}</span>
                </h2>
                <p>Copy, edit, pause, or review a link’s clicks.</p>
              </div>
              <div className="search-field">
                <Search size={18} />
                <input
                  aria-label="Search links on this page"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search this page…"
                />
                <button
                  className="icon-btn"
                  aria-label="Refresh links"
                  title="Refresh links"
                  onClick={() => void refresh()}
                >
                  <RefreshCw size={18} />
                </button>
              </div>
            </div>
            <LinkTable
              links={filtered}
              busy={busy}
              onCopy={copy}
              onToggle={toggle}
              onStats={setStats}
              onEdit={setEditor}
              onDelete={setDeleting}
            />
            {!page && !error && (
              <div className="empty-state" role="status">
                Loading your links…
              </div>
            )}
            {page && filtered.length === 0 && (
              <div className="empty-state">
                <span className="empty-icon">
                  <Link2 size={30} />
                </span>
                <h3>
                  {query
                    ? "No links match your search"
                    : "Create your first short link"}
                </h3>
                <p>
                  {query
                    ? "Try another name, code, or destination on this page."
                    : "Paste a destination URL and choose an ending, or let us generate one."}
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
            <span>Cut the long link. Keep the connection.</span>
            <span>
              Your links, in one place <Link2 size={14} />
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
              onClick={async () => {
                if (deleting && (await remove(deleting))) setDeleting(null);
              }}
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
