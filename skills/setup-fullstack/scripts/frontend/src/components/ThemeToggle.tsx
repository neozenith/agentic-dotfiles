import { Moon, Sun } from "lucide-react";

import { useTheme } from "@/components/ThemeProvider";
import { Button } from "@/components/ui/button";

export const ThemeToggle = () => {
	const { theme, toggle } = useTheme();
	const isDark = theme === "dark";
	return (
		<Button
			type="button"
			variant="ghost"
			size="icon"
			onClick={toggle}
			aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
			data-testid="theme-toggle"
			data-theme={theme}
		>
			{isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
		</Button>
	);
};
