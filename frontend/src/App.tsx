import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { GameDetailPage } from "./pages/GameDetailPage";

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/games/:gamePk" element={<GameDetailPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
