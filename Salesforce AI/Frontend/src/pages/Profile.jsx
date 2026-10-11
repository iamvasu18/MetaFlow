import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Profile() {
  const { user } = useAuth();
  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold">My Profile</h1>
      <p className="mt-2 text-sm text-slate-500">Your account details.</p>
      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-blue-100 text-xl font-semibold text-blue-600">{user?.name?.slice(0, 2).toUpperCase()}</div>
        <dl className="space-y-5"><div><dt className="text-xs text-slate-500">Name</dt><dd className="mt-1 font-medium">{user?.name}</dd></div><div><dt className="text-xs text-slate-500">Email</dt><dd className="mt-1 break-all font-medium">{user?.email}</dd></div></dl>
      </section>
      <Link to="/settings" className="mt-6 inline-block text-sm font-medium text-blue-600">Open Account Settings →</Link>
    </main>
  );
}
