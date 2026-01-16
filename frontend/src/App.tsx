import { Navigate, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Trends from "./pages/Trends";
import Configure from "./pages/Configure";
import Health from "./pages/Health";
import Logs from "./pages/Logs";
import { Layout } from "./components/Layout";

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/trends" element={<Trends />} />
        <Route path="/config" element={<Configure />} />
        <Route path="/health" element={<Health />} />
        <Route path="/logs" element={<Logs />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

export default App;

