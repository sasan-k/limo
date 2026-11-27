/** Engine error envelope message (api.md › Errors), else the HTTP status. */
async function failure(method: string, path: string, response: Response): Promise<Error> {
  const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
  return new Error(body?.error?.message ?? `${method} ${path} failed: ${response.status}`);
}

/** GET a JSON resource from the engine; throws on a non-2xx status. */
export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw await failure("GET", path, response);
  return (await response.json()) as T;
}

/** Send a JSON body to the engine; throws with the engine's error message on a non-2xx status. */
async function sendJson<T>(method: "POST" | "PUT", path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await failure(method, path, response);
  return (await response.json()) as T;
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>("POST", path, body);
}

export function putJson<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>("PUT", path, body);
}
