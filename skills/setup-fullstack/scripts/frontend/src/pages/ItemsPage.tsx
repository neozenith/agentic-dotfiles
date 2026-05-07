import { useEffect, useState } from "react";

import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
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

	return (
		<div data-testid="items-page" className="space-y-6">
			<header className="space-y-2">
				<h1 className="text-3xl font-semibold tracking-tight">Items</h1>
				<p className="text-muted-foreground">
					Records persisted by the FastAPI backend at{" "}
					<code className="text-xs">/api/items</code>.
				</p>
			</header>

			{state.status === "loading" && (
				<p data-testid="items-loading" className="text-sm text-muted-foreground">
					Loading items…
				</p>
			)}

			{state.status === "error" && (
				<Card data-testid="items-error" className="border-destructive">
					<CardHeader>
						<CardTitle className="text-destructive">
							Failed to load items
						</CardTitle>
						<CardDescription>{state.message}</CardDescription>
					</CardHeader>
				</Card>
			)}

			{state.status === "ok" && state.items.length === 0 && (
				<Card data-testid="items-empty">
					<CardHeader>
						<CardTitle>No items yet</CardTitle>
						<CardDescription>
							POST to <code className="text-xs">/api/items</code> to add one.
						</CardDescription>
					</CardHeader>
				</Card>
			)}

			{state.status === "ok" && state.items.length > 0 && (
				<ul data-testid="items-list" className="grid gap-3">
					{state.items.map((item) => (
						<li key={item.id}>
							<Card>
								<CardHeader>
									<CardTitle>{item.name}</CardTitle>
									{item.description && (
										<CardDescription>{item.description}</CardDescription>
									)}
								</CardHeader>
								<CardContent>
									<p className="text-xs text-muted-foreground">
										id: {item.id}
									</p>
								</CardContent>
							</Card>
						</li>
					))}
				</ul>
			)}
		</div>
	);
};
