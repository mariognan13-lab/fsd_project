"use client";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import Link from "next/link";

export default function LoginPage() {
  const router = useRouter();
  const [visible, setVisible] = useState(false);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    router.push("/");
  }

  return (
    <main className="min-h-screen bg-[#080d18] px-5 py-6 text-slate-100 sm:px-8 lg:px-12">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-7xl flex-col">
        <header className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-2xl bg-blue-500 text-lg font-black">â†—</span><b className="tracking-[0.2em]">TRAFFIC IQ</b></Link>
          <Link href="/" className="rounded-xl border border-slate-700 px-3 py-2 text-xs text-slate-300">Back to dashboard</Link>
        </header>

        <section className="grid flex-1 items-center gap-12 py-14 lg:grid-cols-[1fr_460px] lg:gap-24">
          <div>
            <p className="mb-6 text-xs font-bold uppercase tracking-[0.16em] text-blue-300">â— Control room access</p>
            <h1 className="text-5xl font-black text-white sm:text-6xl">See the city <span className="text-blue-400">move.</span></h1>
            <p className="mt-6 max-w-lg text-lg leading-7 text-slate-400">Sign in to your Traffic IQ workspace and keep every route, bottleneck, and mobility signal in view.</p>
            <div className="mt-10 grid grid-cols-3 gap-3">{[["24/7", "Visibility"], ["Live", "Intelligence"], ["1 view", "Every signal"]].map(([value, label]) => <div key={label} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4"><b className="font-mono text-lg text-blue-300">{value}</b><small className="mt-1 block text-[10px] uppercase text-slate-500">{label}</small></div>)}</div>
          </div>

          <div className="rounded-[2rem] border border-slate-700 bg-slate-900/90 p-6 shadow-2xl sm:p-8">
            <p className="text-xs font-bold uppercase tracking-widest text-blue-400">Welcome back</p>
            <h2 className="mt-2 text-2xl font-bold">Sign in to Traffic IQ</h2>
            <p className="mt-2 text-sm text-slate-400">Enter any details to continue to the workspace.</p>
            <form onSubmit={submit} action={() => router.push("/")} className="mt-8 space-y-5">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-400">Work email<input type="email" placeholder="you@company.com" className="mt-2 h-12 w-full rounded-xl border border-slate-700 bg-slate-950 px-4 text-sm text-white outline-none focus:border-blue-500" /></label>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-400">Password<span className="relative mt-2 block"><input type={visible ? "text" : "password"} placeholder="Enter your password" className="h-12 w-full rounded-xl border border-slate-700 bg-slate-950 px-4 pr-16 text-sm text-white outline-none focus:border-blue-500" /><button type="button" onClick={() => setVisible(!visible)} className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500">{visible ? "Hide" : "Show"}</button></span></label>
              <label className="text-xs text-slate-400"><input type="checkbox" defaultChecked className="mr-2 accent-blue-500" />Remember me</label>
              <button type="submit" onClick={(e) => { e.preventDefault(); router.push("/"); }} className="h-12 w-full rounded-xl bg-blue-500 text-sm font-bold text-white">Sign in to workspace</button>
            </form>
            <p className="mt-7 text-center text-sm text-slate-500">Need an account? <button type="button" className="font-bold text-blue-400">Request access</button></p>
          </div>
        </section>

        <footer className="flex justify-between border-t border-slate-800 py-5 text-[10px] uppercase tracking-wider text-slate-600"><span>Â© Traffic IQ</span><span>Live traffic Â· smarter decisions</span></footer>
      </div>
    </main>
  );
}
