export type User = { id: string; email: string };
export type Link = {
  id: string;
  code: string;
  name: string;
  target_url: string;
  enabled: boolean;
  created_at: string;
  total_clicks: number;
};
export type LinkPage = {
  items: Link[];
  total: number;
  active: number;
  total_clicks: number;
};
export type Stats = {
  total_clicks: number;
  days: { day: string; clicks: number }[];
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((e: { msg: string }) => e.msg).join(". ")
          : "Unable to connect. Please try again.";
    throw new ApiError(response.status, message);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const shortUrl = (code: string) => `${window.location.origin}/r/${code}`;
