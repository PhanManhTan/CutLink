import { useCallback, useEffect, useState } from "react";
import Brand from "./components/Brand";
import Auth from "./Auth";
import Dashboard from "./Dashboard";
import { api, ApiError } from "./api";
import type { User } from "./api";
import { errorMessage } from "./utils";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const loggedOut = useCallback(() => setUser(null), []);
  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch((e) => {
        if (!(e instanceof ApiError && e.status === 401))
          setError(errorMessage(e));
      })
      .finally(() => setLoading(false));
  }, []);
  if (loading)
    return (
      <div className="boot-screen">
        <Brand />
        <p role="status">Opening your workspace…</p>
      </div>
    );
  if (error)
    return (
      <div className="boot-screen">
        <Brand />
        <div role="alert">{error}</div>
        <button
          className="btn btn-brand"
          onClick={() => window.location.reload()}
        >
          Reconnect
        </button>
      </div>
    );
  return user ? (
    <Dashboard user={user} loggedOut={loggedOut} />
  ) : (
    <Auth done={setUser} />
  );
}
