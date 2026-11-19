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
          <span className="eyebrow">FEWER CHARACTERS. MORE CONNECTIONS.</span>
          <h1>
            Every great connection
            <br />
            starts with
            <br />
            <span>one small link.</span>
          </h1>
          <p>
            A little space to shorten your links,
            <br />
            share your ideas, and follow every visit.
          </p>
          <div className="auth-link">
            <Link2 size={24} />
            <span>
              cutlink / <strong>your next idea</strong>
            </span>
            <CheckCircle2 size={21} />
          </div>
        </div>
        <small>Simple from the very first link.</small>
      </div>
      <main className="auth-form-wrap">
        <form onSubmit={submit} className="auth-form">
          <span className="eyebrow">YOUR LITTLE CORNER OF THE INTERNET</span>
          <h2>{register ? "Make room for more" : "Welcome back"}</h2>
          <p>
            {register
              ? "Create an account. Give your links a home."
              : "Sign in and pick up where you left off."}
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
            {register ? "Already have an account?" : "New around here?"}{" "}
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
            <Check size={15} /> Your links stay private in your account.
          </p>
        </form>
      </main>
    </div>
  );
}
