import {
  BarChart3,
  Copy,
  ExternalLink,
  Link2,
  Pencil,
  Trash2,
} from "lucide-react";
import type { Link } from "../api";
import { number } from "../utils";

type Props = {
  links: Link[];
  busy: string | null;
  onCopy: (link: Link) => void;
  onToggle: (link: Link) => void;
  onStats: (link: Link) => void;
  onEdit: (link: Link) => void;
  onDelete: (link: Link) => void;
};

export default function LinkTable({
  links,
  busy,
  onCopy,
  onToggle,
  onStats,
  onEdit,
  onDelete,
}: Props) {
  return (
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
          {links.map((link) => (
            <tr key={link.id}>
              <td className="destination-cell">
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
              <td className="short-cell">
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
                    onClick={() => onCopy(link)}
                    aria-label={`Copy ${link.name}`}
                  >
                    <Copy size={16} />
                  </button>
                </div>
              </td>
              <td className="clicks-cell" data-label="Clicks">
                <button
                  className="click-count"
                  onClick={() => onStats(link)}
                  aria-label={`Stats for ${link.name}`}
                >
                  <BarChart3 size={15} />
                  {number.format(link.total_clicks)}
                </button>
              </td>
              <td className="status-cell">
                <button
                  className={`status-badge ${link.enabled ? "enabled" : "disabled"}`}
                  disabled={busy === link.id}
                  onClick={() => onToggle(link)}
                  title="Click to enable or disable"
                  aria-label={`${link.enabled ? "Disable" : "Enable"} ${link.name}`}
                >
                  <span />
                  {link.enabled ? "Active" : "Paused"}
                </button>
              </td>
              <td className="actions-cell">
                <div className="row-actions">
                  <button
                    className="icon-btn"
                    onClick={() => onEdit(link)}
                    aria-label={`Edit ${link.name}`}
                  >
                    <Pencil size={16} />
                    <span className="action-label">Edit</span>
                  </button>
                  <button
                    className="icon-btn delete-btn"
                    onClick={() => onDelete(link)}
                    aria-label={`Delete ${link.name}`}
                  >
                    <Trash2 size={16} />
                    <span className="action-label">Delete</span>
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
