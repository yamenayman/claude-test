export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export async function apiGet(path, params) {
  const url = new URL(`${API_URL}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    });
  }
  const response = await fetch(url.toString());
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data && data.detail ? JSON.stringify(data.detail) : response.statusText;
    throw new Error(detail || "تعذر الاتصال بالخدمة.");
  }
  return data;
}

export async function apiPost(path, body) {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      data && data.detail
        ? typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail)
        : response.statusText;
    throw new Error(detail || "تعذر الاتصال بالخدمة.");
  }
  return data;
}
