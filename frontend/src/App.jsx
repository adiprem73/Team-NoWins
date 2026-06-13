import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import MoodHistory from "./pages/MoodHistory";
import DeviceControl from "./pages/DeviceControl";
import Patterns from "./pages/Patterns";
import Layout from "./components/Layout";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="history" element={<MoodHistory />} />
          <Route path="patterns" element={<Patterns />} />
          <Route path="devices" element={<DeviceControl />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
