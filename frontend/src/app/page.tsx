'use client';

import React from 'react';
import DefectStream from '@/components/DefectStream';
import DashboardStats from '@/components/DashboardStats';

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-bg-0 text-fg flex flex-col p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold font-sans text-sig-cyan">Industrial Vision Dashboard v2</h1>
        <p className="text-fg-2 text-sm">Real-time pipeline monitoring</p>
      </header>

      <main className="flex-1 flex flex-col gap-6">
        {/* Stats & Charts */}
        <section className="lg:col-span-3">
          <DashboardStats />
        </section>

        {/* Realtime Defect Stream */}
        <section className="border border-line rounded-xl p-6 bg-bg-1">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold">Realtime Defect Stream</h2>
            <span className="flex h-2.5 w-2.5 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sig-cyan opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-sig-cyan"></span>
            </span>
          </div>
          <DefectStream />
        </section>
      </main>
    </div>
  );
}
