import { NavLink, Outlet } from "react-router-dom";

function navLinkClass({ isActive }: { isActive: boolean }) {
  return isActive
    ? "rounded-md bg-slate-800 px-3 py-2 text-sm font-medium text-white"
    : "rounded-md px-3 py-2 text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white";
}

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-slate-900 text-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-4 py-4">
          <h1 className="text-lg font-semibold tracking-tight">Splunk Ansible UI</h1>
          <nav className="flex items-center gap-2">
            <NavLink to="/" className={navLinkClass} end>
              Dashboard
            </NavLink>
            <NavLink to="/run" className={navLinkClass}>
              Run Job
            </NavLink>
            <NavLink to="/history" className={navLinkClass}>
              History
            </NavLink>
            <NavLink to="/apps" className={navLinkClass}>
              Apps
            </NavLink>
            <NavLink to="/settings" className={navLinkClass}>
              Settings
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
