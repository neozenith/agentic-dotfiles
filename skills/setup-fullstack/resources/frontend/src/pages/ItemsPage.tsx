import { useEffect, useState } from "react";

import { type Item, listItems } from "@/lib/api";

type LoadState =
	| { status: "loading" }
	| { status: "ok"; items: Item[] }
	| { status: "error"; message: string };

export const ItemsPage = () => {
	const [state, setState] = useState<LoadState>({ status: "loading" });

	useEffect(() => {
		listItems()
			.then((items) => setState({ status: "ok", items }))
			.catch((err: unknown) => {
				const message = err instanceof Error ? err.message : String(err);
				setState({ status: "error", message });
			});
	}, []);

	if (state.status === "loading") {
		return (
			<div data-testid="items-loading" className="text-muted-foreground">
				Loading items…
			</div>
		);
	}
	if (state.status === "error") {
		return (
			<div data-testid="items-error" className="text-destructive">
				Failed to load items: {state.message}
			</div>
		);
	}

	return (
		<div data-testid="items-page" className="space-y-3">
			<h1 className="text-2xl font-semibold">Items</h1>
			{state.items.length === 0 ? (
				<p data-testid="items-empty" className="text-muted-foreground">
					No items yet. POST to <code>/api/items</code> to add one.
				</p>
			) : (
				<ul data-testid="items-list" className="space-y-2">
					{state.items.map((item) => (
						<li key={item.id} className="rounded border p-3">
							<div className="font-medium">{item.name}</div>
							{item.description && (
								<div className="text-sm text-muted-foreground">
									{item.description}
								</div>
							)}
						</li>
					))}
				</ul>
			)}
		</div>
	);
};
