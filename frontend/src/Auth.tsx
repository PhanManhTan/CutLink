import { useState } from "react";
import type { FormEvent } from "react";
import { Check, CheckCircle2, Link2 } from "lucide-react";
import Brand from "./components/Brand";
import { api } from "./api";
import type { User } from "./api";
import { errorMessage } from "./utils";

export default function Auth({ done }: { done: (user: User) => void }) {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      done(
        await api<User>(`/auth/${register ? "register" : "login"}`, "POST", {
          email: form.get("email"),
          password: form.get("password"),
        }),
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-page">
      <div className="auth-story">
        <Brand />
        <div>
          <span className="eyebrow">SHORTEN. SHARE. TRACK.</span>
          <h1>
            Cut the long link.
            <br />
            <span>Keep the connection.</span>
          </h1>
          <p>
            Turn long URLs into short links you can manage, share, and measure.
          </p>
          <div className="auth-link">
            <Link2 size={24} />
            <span>
              /r/<strong>your-custom-link</strong>
            </span>
            <CheckCircle2 size={21} />
          </div>
        </div>
        <small>Short links. Clear insights.</small>
      </div>
      <main className="auth-form-wrap">
        <form onSubmit={submit} className="auth-form">
          <span className="eyebrow">YOUR LINK WORKSPACE</span>
          <h2>{register ? "Create your account" : "Welcome back"}</h2>
          <p>
            {register
              ? "Save your links and track their clicks in one place."
              : "Sign in to manage your links and view their clicks."}
          </p>
          {error && (
            <div role="alert" className="alert alert-danger">
              {error}
            </div>
          )}
          <label htmlFor="email">Email address</label>
          <input
            id="email"
            name="email"
            className="form-control"
            type="email"
            autoComplete="email"
            maxLength={320}
            placeholder="you@example.com"
            required
          />
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            className="form-control"
            type="password"
            autoComplete={register ? "new-password" : "current-password"}
            minLength={10}
            maxLength={128}
            placeholder="At least 10 characters"
            required
          />
          <button className="btn btn-brand w-100 auth-submit" disabled={busy}>
            {busy ? "Please wait…" : register ? "Create account" : "Sign in"}
          </button>
          <div className="auth-switch">
            {register ? "Already have an account?" : "Don’t have an account?"}{" "}
            <button
              type="button"
              onClick={() => {
                setRegister(!register);
                setError("");
              }}
            >
              {register ? "Sign in" : "Create an account"}
            </button>
          </div>
          <p className="auth-footnote">
            <Check size={15} /> Only you can manage your links. Short links are
            public.
          </p>
        </form>
      </main>
    </div>
  );
}
