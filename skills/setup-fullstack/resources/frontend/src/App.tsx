import { BrowserRouter, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { HomePage } from "@/pages/HomePage";
import { ItemsPage } from "@/pages/ItemsPage";
import { NotesPage } from "@/pages/NotesPage";

const App = () => (
	<BrowserRouter>
		<Routes>
			<Route element={<Layout />}>
				<Route index element={<HomePage />} />
				<Route path="items" element={<ItemsPage />} />
				<Route path="notes" element={<NotesPage />} />
			</Route>
		</Routes>
	</BrowserRouter>
);

export default App;
