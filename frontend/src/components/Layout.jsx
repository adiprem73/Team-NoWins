import { Outlet, NavLink } from "react-router-dom";
import { Brain, History, Lightbulb, Network } from "lucide-react";

export default function Layout() {
  const linkClass = ({ isActive }) =>
    `flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
      isActive
        ? "bg-indigo-600 text-white"
        : "text-gray-400 hover:text-white hover:bg-gray-800"
    }`;

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 border-r border-gray-800 p-6 flex flex-col">
        <div className="mb-8">
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Brain className="w-6 h-6 text-indigo-400" />
            MoodSense AI
          </h1>
          <p className="text-xs text-gray-500 mt-1">Smart Environment Control</p>
        </div>

        <nav className="flex flex-col gap-2">
          <NavLink to="/" className={linkClass}>
            <Brain className="w-4 h-4" />
            Dashboard
          </NavLink>
          <NavLink to="/patterns" className={linkClass}>
            <Network className="w-4 h-4" />
            Patterns
          </NavLink>
          <NavLink to="/history" className={linkClass}>
            <History className="w-4 h-4" />
            Mood History
          </NavLink>
          <NavLink to="/devices" className={linkClass}>
            <Lightbulb className="w-4 h-4" />
            Devices
          </NavLink>
        </nav>

        <div className="mt-auto pt-4 border-t border-gray-800">
          <p className="text-xs text-gray-600">Powered by Voxtral on Bedrock</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-8 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
