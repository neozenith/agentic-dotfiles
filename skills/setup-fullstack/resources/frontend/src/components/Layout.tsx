import {
	ChevronLeft,
	ChevronRight,
	FileText,
	Home,
	Package,
} from "lucide-react";
import { type ComponentType, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";

import { ThemeToggle } from "@/components/ThemeToggle";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface NavItem {
	to: string;
	label: string;
	icon: ComponentType<{ className?: string }>;
}

const NAV: NavItem[] = [
	{ to: "/", label: "Home", icon: Home },
	{ to: "/items", label: "Items", icon: Package },
	{ to: "/notes", label: "Notes", icon: FileText },
];

const navTestId = (to: string): string => {
	const slug = to.replace(/\W/g, "");
	return `nav-${slug || "home"}`;
};

const sectionTitle = (pathname: string): string => {
	const match = NAV.find((item) => item.to === pathname);
	return match?.label ?? "App";
};

export const Layout = () => {
	const [collapsed, setCollapsed] = useState(false);
	const { pathname } = useLocation();

	return (
		<div className="flex h-screen overflow-hidden bg-background text-foreground">
			<aside
				data-testid="sidebar"
				data-collapsed={String(collapsed)}
				className={cn(
					"flex flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-[width] duration-200 ease-in-out",
					collapsed ? "w-[3.75rem]" : "w-60",
				)}
			>
				<div className="flex h-14 items-center justify-between gap-2 border-b border-sidebar-border px-3">
					{!collapsed && (
						<span className="select-none text-sm font-semibold tracking-tight">
							Fullstack
						</span>
					)}
					<Button
						type="button"
						variant="ghost"
						size="icon"
						data-testid="sidebar-toggle"
						onClick={() => setCollapsed((c) => !c)}
						aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
						className="ml-auto h-8 w-8"
					>
						{collapsed ? (
							<ChevronRight className="h-4 w-4" />
						) : (
							<ChevronLeft className="h-4 w-4" />
						)}
					</Button>
				</div>
				<nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
					{NAV.map((item) => {
						const Icon = item.icon;
						const active = pathname === item.to;
						return (
							<Link
								key={item.to}
								to={item.to}
								data-testid={navTestId(item.to)}
								aria-current={active ? "page" : undefined}
								className={cn(
									buttonVariants({
										variant: active ? "secondary" : "ghost",
										size: "sm",
									}),
									"justify-start gap-3 px-3",
									collapsed && "justify-center px-0",
								)}
							>
								<Icon className="h-4 w-4 shrink-0" />
								{!collapsed && <span>{item.label}</span>}
							</Link>
						);
					})}
				</nav>
				<div className="flex items-center justify-between gap-2 border-t border-sidebar-border p-2">
					{!collapsed && (
						<span className="px-2 text-xs text-muted-foreground">Theme</span>
					)}
					<ThemeToggle />
				</div>
			</aside>
			<div className="flex flex-1 flex-col overflow-hidden">
				<header className="flex h-14 items-center gap-3 border-b bg-background/60 px-6 backdrop-blur-sm">
					<h1 className="text-base font-medium tracking-tight">
						{sectionTitle(pathname)}
					</h1>
				</header>
				<main data-testid="main" className="flex-1 overflow-auto">
					<div className="mx-auto w-full max-w-4xl p-6">
						<Outlet />
					</div>
				</main>
			</div>
		</div>
	);
};
