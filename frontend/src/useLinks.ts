import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, shortUrl } from "./api";
import type { Link, LinkPage } from "./api";
import { errorMessage } from "./utils";

// The hook owns requests/state; components only render the workspace and collect input.
export function useLinks(loggedOut: () => void) {
  const [page, setPage] = useState<LinkPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const requestId = useRef(0);
  const refresh = useCallback(async () => {
    const id = ++requestId.current;
    try {
      const data = await api<LinkPage>(`/links?limit=20&offset=${offset}`);
      if (id === requestId.current) {
        setPage(data);
        setError("");
      }
    } catch (e) {
      if (id !== requestId.current) return;
      if (e instanceof ApiError && e.status === 401) loggedOut();
      else setError(errorMessage(e));
    }
  }, [offset, loggedOut]);

  useEffect(() => {
    void refresh();
    window.addEventListener("focus", refresh);
    return () => {
      requestId.current++;
      window.removeEventListener("focus", refresh);
    };
  }, [refresh]);
  useEffect(() => {
    if (page && offset > 0 && !page.items.length)
      setOffset(Math.max(0, offset - 20));
  }, [page, offset]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 3500);
    return () => clearTimeout(timer);
  }, [notice]);

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
  async function remove(link: Link) {
    setBusy(link.id);
    try {
      await api(`/links/${link.id}`, "DELETE");
      setNotice("Link deleted.");
      await refresh();
      return true;
    } catch (e) {
      setError(errorMessage(e));
      return false;
    } finally {
      setBusy(null);
    }
  }
  return {
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
  };
}
