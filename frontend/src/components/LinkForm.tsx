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
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await api(
        link ? `/links/${link.id}` : "/links",
        link ? "PATCH" : "POST",
        { name: form.get("name"), target_url: form.get("url") },
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
          pattern="https?://.*"
          maxLength={4096}
          defaultValue={link?.target_url}
          placeholder="https://example.com/your-next-idea"
          required
        />
        <p className="field-note">HTTP and HTTPS links are supported.</p>
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
