import { useEffect, useState } from "react";
import Modal from "./Modal";
import { api } from "../api";
import type { Link, Stats } from "../api";
import { errorMessage, number } from "../utils";

export default function StatsDialog({
  link,
  close,
}: {
  link: Link;
  close: () => void;
}) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<Stats>(`/links/${link.id}/stats`)
      .then((data) => {
        if (active) setStats(data);
      })
      .catch((e) => {
        if (active) setError(errorMessage(e));
      });
    return () => {
      active = false;
    };
  }, [link.id]);
  const max = Math.max(1, ...(stats?.days.map((day) => day.clicks) || []));
  return (
    <Modal title="Link analytics" close={close}>
      <p className="muted">{link.name} · Last 30 days (UTC)</p>
      {error && (
        <div role="alert" className="alert alert-danger">
          {error}
        </div>
      )}
      {!stats && !error && <p role="status">Loading your stats…</p>}
      {stats && (
        <>
          <div className="stat-total">
            {number.format(stats.total_clicks)}
            <span> total clicks</span>
          </div>
          <div
            className="click-chart"
            role="img"
            aria-label="Clicks over the past 30 days"
          >
            <div className="chart-grid" />
            {stats.days.map((day) => (
              <div
                className="chart-column"
                key={day.day}
                title={`${day.day}: ${day.clicks} click`}
              >
                <div
                  style={{
                    height: `${(day.clicks / max) * 100}%`,
                    minHeight: day.clicks ? 4 : 2,
                  }}
                />
              </div>
            ))}
          </div>
          <div className="chart-labels">
            <span>{stats.days[0].day}</span>
            <span>{stats.days[29].day}</span>
          </div>
          <p className="field-note">
            Daily data refreshes every minute. Total clicks include processed
            events.
          </p>
          <details>
            <summary>View daily data</summary>
            <div className="daily-data">
              <table className="table table-sm">
                <thead>
                  <tr>
                    <th>Date (UTC)</th>
                    <th>Clicks</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.days.map((d) => (
                    <tr key={d.day}>
                      <td>{d.day}</td>
                      <td>{d.clicks}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </Modal>
  );
}
