import { useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";

import { cn } from "@/lib/utils";

interface NavItem {
	to: string;
	label: string;
	short: string;
}

const NAV: NavItem[] = [
	{ to: "/", label: "Home", short: "H" },
	{ to: "/items", label: "Items", short: "I" },
	{ to: "/notes", label: "Notes", short: "N" },
];

const navTestId = (to: string): string => {
	const slug = to.replace(/\W/g, "");
	return `nav-${slug || "home"}`;
};

export const Layout = () => {
	const [collapsed, setCollapsed] = useState(false);
	const { pathname } = useLocation();

	return (
		<div className="flex h-screen text-sm">
			<aside
				data-testid="sidebar"
				data-collapsed={String(collapsed)}
				className={cn(
					"flex flex-col border-r bg-muted/40 transition-[width] duration-200 ease-in-out",
					collapsed ? "w-14" : "w-56",
				)}
			>
				<div className="flex items-center justify-between p-2">
					{!collapsed && <span className="px-2 font-semibold">App</span>}
					<button
						type="button"
						data-testid="sidebar-toggle"
						onClick={() => setCollapsed((c) => !c)}
						aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
						className="rounded px-2 py-1 hover:bg-accent"
					>
						{collapsed ? "›" : "‹"}
					</button>
				</div>
				<nav className="flex flex-col gap-1 p-2">
					{NAV.map((item) => {
						const active = pathname === item.to;
						return (
							<Link
								key={item.to}
								to={item.to}
								data-testid={navTestId(item.to)}
								className={cn(
									"rounded px-3 py-2 transition-colors",
									active
										? "bg-accent font-medium text-accent-foreground"
										: "hover:bg-accent/50",
									collapsed && "text-center",
								)}
							>
								{collapsed ? item.short : item.label}
							</Link>
						);
					})}
				</nav>
			</aside>
			<main data-testid="main" className="flex-1 overflow-auto p-6">
				<Outlet />
			</main>
		</div>
	);
};
