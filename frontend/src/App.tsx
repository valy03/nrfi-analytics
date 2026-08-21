import { BrowserRouter, Route, Routes } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { AboutPage } from "./pages/AboutPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { Dashboard } from "./pages/Dashboard";
import { GameDetailPage } from "./pages/GameDetailPage";
import { HistoryPage } from "./pages/HistoryPage";

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50">
        <NavBar />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/games/:gamePk" element={<GameDetailPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/about" element={<AboutPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
