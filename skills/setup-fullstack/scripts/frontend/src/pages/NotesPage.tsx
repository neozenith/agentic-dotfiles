import { useEffect, useState } from "react";

import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
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

	return (
		<div data-testid="notes-page" className="space-y-6">
			<header className="space-y-2">
				<h1 className="text-3xl font-semibold tracking-tight">Notes</h1>
				<p className="text-muted-foreground">
					Records persisted by the FastAPI backend at{" "}
					<code className="text-xs">/api/notes</code>.
				</p>
			</header>

			{state.status === "loading" && (
				<p data-testid="notes-loading" className="text-sm text-muted-foreground">
					Loading notes…
				</p>
			)}

			{state.status === "error" && (
				<Card data-testid="notes-error" className="border-destructive">
					<CardHeader>
						<CardTitle className="text-destructive">
							Failed to load notes
						</CardTitle>
						<CardDescription>{state.message}</CardDescription>
					</CardHeader>
				</Card>
			)}

			{state.status === "ok" && state.notes.length === 0 && (
				<Card data-testid="notes-empty">
					<CardHeader>
						<CardTitle>No notes yet</CardTitle>
						<CardDescription>
							POST to <code className="text-xs">/api/notes</code> to add one.
						</CardDescription>
					</CardHeader>
				</Card>
			)}

			{state.status === "ok" && state.notes.length > 0 && (
				<ul data-testid="notes-list" className="grid gap-3">
					{state.notes.map((note) => (
						<li key={note.id}>
							<Card>
								<CardHeader>
									<CardTitle>{note.title}</CardTitle>
								</CardHeader>
								{note.body && (
									<CardContent>
										<pre className="whitespace-pre-wrap text-sm text-muted-foreground">
											{note.body}
										</pre>
									</CardContent>
								)}
							</Card>
						</li>
					))}
				</ul>
			)}
		</div>
	);
};
