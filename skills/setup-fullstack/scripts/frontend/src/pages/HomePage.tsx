import { Database, FileText, Package } from "lucide-react";

import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

export const HomePage = () => (
	<div data-testid="home-page" className="space-y-8">
		<header className="space-y-2">
			<h1 className="text-3xl font-semibold tracking-tight">Welcome</h1>
			<p className="max-w-2xl text-base text-muted-foreground">
				Fullstack scaffold: FastAPI + uv backend (async, SQLite or Postgres)
				wired to a Vite + React + TypeScript frontend with shadcn/ui design
				tokens and a light/dark theme toggle. Two example data models so the
				whole stack — DB, API, types, UI — is wired end-to-end on day one.
			</p>
		</header>
		<section className="grid gap-4 md:grid-cols-2">
			<Card className="transition-shadow hover:shadow-md">
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<Package className="h-5 w-5 text-muted-foreground" /> Items
					</CardTitle>
					<CardDescription>
						CRUD over <code className="text-xs">/api/items</code>.
					</CardDescription>
				</CardHeader>
				<CardContent className="text-sm text-muted-foreground">
					Click <strong className="text-foreground">Items</strong> in the sidebar.
				</CardContent>
			</Card>
			<Card className="transition-shadow hover:shadow-md">
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<FileText className="h-5 w-5 text-muted-foreground" /> Notes
					</CardTitle>
					<CardDescription>
						CRUD over <code className="text-xs">/api/notes</code>.
					</CardDescription>
				</CardHeader>
				<CardContent className="text-sm text-muted-foreground">
					Click <strong className="text-foreground">Notes</strong> in the sidebar.
				</CardContent>
			</Card>
		</section>
		<section className="rounded-lg border bg-card p-5 text-card-foreground">
			<div className="flex items-start gap-3">
				<Database className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
				<div className="space-y-1">
					<h2 className="text-sm font-semibold">Database</h2>
					<p className="text-sm text-muted-foreground">
						Backed by SQLAlchemy with async drivers — <code>aiosqlite</code> or{" "}
						<code>asyncpg</code>. Switch backends with{" "}
						<code className="text-xs">
							make DATABASE_BACKEND=postgres docker-up
						</code>
						.
					</p>
				</div>
			</div>
		</section>
	</div>
);
