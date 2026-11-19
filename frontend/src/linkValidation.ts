export function validateDestination(value: string): string {
  const url = value.trim();
  if (!url) return "Enter a destination URL.";
  if (!/^https?:\/\//i.test(url))
    return "Enter a full URL starting with http:// or https://.";
  if (/[\x00-\x1f\x7f]/.test(url))
    return "Remove line breaks and control characters from the URL.";
  try {
    const parsed = new URL(url);
    if (!parsed.hostname) return "Enter a URL with a valid website address.";
    if (parsed.username || parsed.password)
      return "Remove the username or password from the URL.";
    if (parsed.toString().length > 4096)
      return "The destination URL is too long (maximum 4096 characters).";
  } catch {
    return "This URL is not valid. Check the website address and port.";
  }
  return "";
}

export function validateCustomCode(value: string): string {
  const code = value.trim();
  if (code && !/^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$/.test(code)) {
    return "Use 3–64 letters, numbers, hyphens or underscores. Start with a letter or number.";
  }
  return "";
}

export function validateName(value: string): string {
  return value.trim() ? "" : "Give this link a name so you can find it later.";
}
