// API client — single fetch boundary for the frontend.
//
// Always use relative `/api/...` paths so the Vite proxy (dev) or the
// FastAPI static mount (production / Docker) can route appropriately.
// Never hardcode `localhost:8200` or any other absolute backend URL.

export interface Item {
	id: number;
	name: string;
	description: string;
	created_at: string;
}

export interface Note {
	id: number;
	title: string;
	body: string;
	created_at: string;
}

const apiFetch = async <T>(path: string, init?: RequestInit): Promise<T> => {
	const res = await fetch(`/api${path}`, init);
	if (!res.ok) {
		const text = await res.text().catch(() => "");
		throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
	}
	return (await res.json()) as T;
};

export const listItems = (): Promise<Item[]> => apiFetch<Item[]>("/items");

export const createItem = (payload: {
	name: string;
	description?: string;
}): Promise<Item> =>
	apiFetch<Item>("/items", {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify(payload),
	});

export const listNotes = (): Promise<Note[]> => apiFetch<Note[]>("/notes");

export const createNote = (payload: {
	title: string;
	body?: string;
}): Promise<Note> =>
	apiFetch<Note>("/notes", {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify(payload),
	});
