import React from 'react';
import { Outlet } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useUIStore } from '@/stores/uiStore';

/**
 * Main Application Shell
 * Contains sidebar navigation and header, wraps all protected pages
 */
export const AppShell: React.FC = () => {
  const sidebarOpen = useUIStore((state) => state.sidebarOpen);

  return (
    <div className="min-h-screen bg-base">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <motion.div
        animate={{
          marginLeft: sidebarOpen ? 280 : 0,
        }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className="min-h-screen flex flex-col lg:ml-[280px]"
      >
        {/* Header */}
        <Header />

        {/* Page Content */}
        <main className="flex-1">
          <Outlet />
        </main>
      </motion.div>
    </div>
  );
};

export default AppShell;
