import { useState } from "react";
import type { FormEvent } from "react";
import Modal from "./Modal";
import { api, ApiError } from "../api";
import type { Link } from "../api";
import { errorMessage } from "../utils";
import {
  validateCustomCode,
  validateDestination,
  validateName,
} from "../linkValidation";

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
  const [targetUrl, setTargetUrl] = useState(link?.target_url || "");
  const [validation, setValidation] = useState({ name: "", url: "", code: "" });
  const prefix = `${window.location.origin}/r/`;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const errors = {
        name: validateName(String(form.get("name") || "")),
        url: validateDestination(targetUrl),
        code: link ? "" : validateCustomCode(customCode),
      };
      setValidation(errors);
      if (errors.name || errors.url || errors.code) {
        document
          .getElementById(
            errors.name ? "link-name" : errors.url ? "link-url" : "custom-code",
          )
          ?.focus();
        return;
      }
      await api(
        link ? `/links/${link.id}` : "/links",
        link ? "PATCH" : "POST",
        {
          name: form.get("name"),
          target_url: targetUrl.trim(),
          ...(!link && { custom_code: customCode.trim() || null }),
        },
      );
      saved();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && !link) {
        setValidation((previous) => ({ ...previous, code: e.message }));
      } else {
        setError(errorMessage(e));
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={link ? "Edit link" : "Create a short link"} close={close}>
      <form onSubmit={submit} noValidate>
        <p className="muted">
          Paste a destination URL, then choose an ending or let us generate one.
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
          className={`form-control ${validation.name ? "is-invalid" : ""}`}
          maxLength={120}
          defaultValue={link?.name}
          placeholder="e.g. My creative portfolio"
          required
          aria-invalid={!!validation.name}
          aria-describedby={validation.name ? "name-error" : undefined}
          onBlur={(event) =>
            setValidation((previous) => ({
              ...previous,
              name: validateName(event.target.value),
            }))
          }
        />
        {validation.name && (
          <div id="name-error" className="invalid-feedback" role="alert">
            {validation.name}
          </div>
        )}
        <label htmlFor="link-url">Destination URL</label>
        <input
          id="link-url"
          name="url"
          className={`form-control ${validation.url ? "is-invalid" : ""}`}
          type="url"
          pattern="[Hh][Tt][Tt][Pp][Ss]?://.*"
          maxLength={4096}
          value={targetUrl}
          onChange={(event) => {
            setTargetUrl(event.target.value);
            if (validation.url)
              setValidation((previous) => ({
                ...previous,
                url: validateDestination(event.target.value),
              }));
          }}
          onBlur={() =>
            setValidation((previous) => ({
              ...previous,
              url: validateDestination(targetUrl),
            }))
          }
          aria-invalid={!!validation.url}
          aria-describedby={validation.url ? "url-error" : "url-help"}
          placeholder="https://example.com/your-next-idea"
          required
        />
        {validation.url && (
          <div id="url-error" className="invalid-feedback" role="alert">
            {validation.url}
          </div>
        )}
        <p id="url-help" className="field-note">
          Use a full URL, such as https://example.com/page.
        </p>
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
                className={`form-control ${validation.code ? "is-invalid" : ""}`}
                value={customCode}
                onChange={(event) => {
                  setCustomCode(event.target.value);
                  if (validation.code)
                    setValidation((previous) => ({
                      ...previous,
                      code: validateCustomCode(event.target.value),
                    }));
                }}
                onBlur={() =>
                  setValidation((previous) => ({
                    ...previous,
                    code: validateCustomCode(customCode),
                  }))
                }
                pattern="[A-Za-z0-9][A-Za-z0-9_\-]{2,63}"
                maxLength={64}
                placeholder="your-custom-link"
                autoComplete="off"
                spellCheck={false}
                aria-describedby={
                  validation.code
                    ? "code-error custom-code-help"
                    : "custom-code-help"
                }
                aria-invalid={!!validation.code}
                title="3–64 letters, numbers, hyphens or underscores. Start with a letter or number."
              />
            </div>
            {validation.code && (
              <div
                id="code-error"
                className="invalid-feedback d-block"
                role="alert"
              >
                {validation.code}
              </div>
            )}
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
