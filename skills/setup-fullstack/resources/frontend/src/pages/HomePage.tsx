export const HomePage = () => (
	<div data-testid="home-page" className="space-y-3">
		<h1 className="text-2xl font-semibold">Welcome</h1>
		<p className="text-muted-foreground">
			This is a fullstack scaffold: FastAPI + uv backend, Vite + React + TypeScript
			frontend, with SQLAlchemy persisting two example data models (Items and
			Notes). Use the sidebar to explore.
		</p>
		<ul className="list-disc pl-6 text-muted-foreground">
			<li>
				<strong>Items</strong> — basic CRUD over the <code>/api/items</code> endpoint.
			</li>
			<li>
				<strong>Notes</strong> — basic CRUD over the <code>/api/notes</code> endpoint.
			</li>
		</ul>
	</div>
);
