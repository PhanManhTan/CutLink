import { useState } from "react";
import type { FormEvent } from "react";
import Modal from "./Modal";
import { api } from "../api";
import type { Link } from "../api";
import { errorMessage } from "../utils";

export default function LinkForm({
  link,
  saved,
  close,
}: {
  link?: Link;
  saved: () => void;
  close: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [customCode, setCustomCode] = useState("");
  const prefix = `${window.location.origin}/r/`;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const targetUrl = String(form.get("url") || "").trim();
      let parsed: URL;
      try {
        parsed = new URL(targetUrl);
      } catch {
        setError("Enter a valid URL starting with http:// or https://.");
        return;
      }
      if (
        !/^https?:\/\//i.test(targetUrl) ||
        !["http:", "https:"].includes(parsed.protocol) ||
        !parsed.hostname ||
        parsed.username ||
        parsed.password ||
        /[\x00-\x1f\x7f]/.test(targetUrl)
      ) {
        setError(
          "Enter a valid HTTP or HTTPS URL without a username or password.",
        );
        return;
      }
      await api(
        link ? `/links/${link.id}` : "/links",
        link ? "PATCH" : "POST",
        {
          name: form.get("name"),
          target_url: targetUrl,
          ...(!link && { custom_code: customCode.trim() || null }),
        },
      );
      saved();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={link ? "Edit link" : "A small link. A new connection."}
      close={close}
    >
      <form onSubmit={submit}>
        <p className="muted">
          Give it a name and add the destination you want to share.
        </p>
        {error && (
          <div role="alert" className="alert alert-danger">
            {error}
          </div>
        )}
        <label htmlFor="link-name">Link name</label>
        <input
          autoFocus
          id="link-name"
          name="name"
          className="form-control"
          maxLength={120}
          defaultValue={link?.name}
          placeholder="e.g. My creative portfolio"
          required
        />
        <label htmlFor="link-url">Destination URL</label>
        <input
          id="link-url"
          name="url"
          className="form-control"
          type="url"
          pattern="[Hh][Tt][Tt][Pp][Ss]?://.*"
          maxLength={4096}
          defaultValue={link?.target_url}
          placeholder="https://example.com/your-next-idea"
          required
        />
        <p className="field-note">HTTP and HTTPS links are supported.</p>
        {!link ? (
          <>
            <label htmlFor="custom-code">
              Custom ending{" "}
              <span className="fw-normal text-secondary">(optional)</span>
            </label>
            <div className="short-code-input">
              <span>{prefix}</span>
              <input
                id="custom-code"
                name="custom_code"
                className="form-control"
                value={customCode}
                onChange={(event) => setCustomCode(event.target.value)}
                pattern="[A-Za-z0-9][A-Za-z0-9_\-]{2,63}"
                maxLength={64}
                placeholder="your-custom-link"
                autoComplete="off"
                spellCheck={false}
                aria-describedby="custom-code-help"
                title="3–64 letters, numbers, hyphens or underscores. Start with a letter or number."
              />
            </div>
            <p id="custom-code-help" className="field-note">
              Leave blank for a random 8-character ending. Custom endings use
              3–64 letters, numbers, hyphens or underscores and start with a
              letter or number. Endings are case-sensitive.
            </p>
            <p className="short-code-preview">
              Your short link:{" "}
              <strong>
                {prefix}
                {customCode || "random-code"}
              </strong>
            </p>
          </>
        ) : (
          <>
            <label>Short link</label>
            <p className="short-code-preview">
              {prefix}
              {link.code}
            </p>
          </>
        )}
        <div className="dialog-actions">
          <button type="button" className="btn btn-light" onClick={close}>
            Cancel
          </button>
          <button className="btn btn-brand" disabled={busy}>
            {busy ? "Saving…" : link ? "Save changes" : "Create short link"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
