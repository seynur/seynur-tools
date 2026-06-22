import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import AppsManager from "./pages/AppsManager";
import Dashboard from "./pages/Dashboard";
import JobHistory from "./pages/JobHistory";
import RunJob from "./pages/RunJob";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/run" element={<RunJob />} />
          <Route path="/history" element={<JobHistory />} />
          <Route path="/apps" element={<AppsManager />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
