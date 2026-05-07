import { BrowserRouter, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { ThemeProvider } from "@/components/ThemeProvider";
import { HomePage } from "@/pages/HomePage";
import { ItemsPage } from "@/pages/ItemsPage";
import { NotesPage } from "@/pages/NotesPage";

const App = () => (
	<ThemeProvider>
		<BrowserRouter>
			<Routes>
				<Route element={<Layout />}>
					<Route index element={<HomePage />} />
					<Route path="items" element={<ItemsPage />} />
					<Route path="notes" element={<NotesPage />} />
				</Route>
			</Routes>
		</BrowserRouter>
	</ThemeProvider>
);

export default App;
