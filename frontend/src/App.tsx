import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type HealthResponse = {
  status: string;
  service: string;
};

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => res.json())
      .then(setHealth)
      .catch(() => setError("Could not reach the API"));
  }, []);

  return (
    <div className="min-h-screen bg-white flex items-center justify-center">
      <div className="text-center space-y-3">
        <h1 className="text-2xl font-medium text-gray-900">NRFI Analytics</h1>
        <p className="text-gray-500">
          M0 scaffold — dashboard build starts at M9.
        </p>
        <p className="text-sm">
          {error && <span className="text-red-600">{error}</span>}
          {health && (
            <span className="text-green-700">
              API reachable — {health.service} says "{health.status}"
            </span>
          )}
          {!error && !health && (
            <span className="text-gray-400">Checking API connection…</span>
          )}
        </p>
      </div>
    </div>
  );
}

export default App;
