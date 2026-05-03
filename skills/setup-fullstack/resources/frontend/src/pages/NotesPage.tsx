import { useEffect, useState } from "react";

import { listNotes, type Note } from "@/lib/api";

type LoadState =
	| { status: "loading" }
	| { status: "ok"; notes: Note[] }
	| { status: "error"; message: string };

export const NotesPage = () => {
	const [state, setState] = useState<LoadState>({ status: "loading" });

	useEffect(() => {
		listNotes()
			.then((notes) => setState({ status: "ok", notes }))
			.catch((err: unknown) => {
				const message = err instanceof Error ? err.message : String(err);
				setState({ status: "error", message });
			});
	}, []);

	if (state.status === "loading") {
		return (
			<div data-testid="notes-loading" className="text-muted-foreground">
				Loading notes…
			</div>
		);
	}
	if (state.status === "error") {
		return (
			<div data-testid="notes-error" className="text-destructive">
				Failed to load notes: {state.message}
			</div>
		);
	}

	return (
		<div data-testid="notes-page" className="space-y-3">
			<h1 className="text-2xl font-semibold">Notes</h1>
			{state.notes.length === 0 ? (
				<p data-testid="notes-empty" className="text-muted-foreground">
					No notes yet. POST to <code>/api/notes</code> to add one.
				</p>
			) : (
				<ul data-testid="notes-list" className="space-y-2">
					{state.notes.map((note) => (
						<li key={note.id} className="rounded border p-3">
							<div className="font-medium">{note.title}</div>
							{note.body && (
								<pre className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
									{note.body}
								</pre>
							)}
						</li>
					))}
				</ul>
			)}
		</div>
	);
};
