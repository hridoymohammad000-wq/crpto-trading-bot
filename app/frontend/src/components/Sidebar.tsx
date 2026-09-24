import React from 'react';
import {
  Activity,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  Radio,
  ScanSearch,
  Sliders,
  Terminal,
} from 'lucide-react';
import { NavigationTab } from '../types';

interface SidebarProps {
  currentTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
  positionsCount: number;
  signalsCount: number;
}

interface NavItem {
  id: NavigationTab;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  badge?: number | string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  isCollapsed,
  onToggleCollapse,
  isMobileOpen,
  onCloseMobile,
  positionsCount,
  signalsCount,
}) => {
  const navItems: NavItem[] = [
    { id: 'Dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'Scanner', label: 'Scanner', icon: ScanSearch },
    { id: 'Signals', label: 'Signals', icon: Radio, badge: signalsCount },
    {
      id: 'Active Trade & History',
      label: 'Active Trade & History',
      icon: Activity,
      badge: positionsCount,
    },
    {
      id: 'Performance & Strategy',
      label: 'Performance & Strategy',
      icon: BarChart3,
    },
    { id: 'Settings', label: 'Settings', icon: Sliders },
  ];

  const handleTabClick = (tab: NavigationTab) => {
    onSelectTab(tab);
    if (isMobileOpen) onCloseMobile();
  };

  return (
    <>
      {isMobileOpen && (
        <div
          id="sidebar-mobile-backdrop"
          onClick={onCloseMobile}
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-40 md:hidden"
        />
      )}

      <aside
        id="app-sidebar"
        className={`fixed md:static inset-y-0 left-0 z-40 shrink-0 bg-slate-950 border-r border-slate-800 flex flex-col justify-between transition-all duration-200 ease-in-out ${
          isMobileOpen ? 'translate-x-0 w-72' : '-translate-x-full md:translate-x-0'
        } ${isCollapsed ? 'md:w-16' : 'md:w-64'}`}
      >
        <div className="p-3 space-y-1">
          <div
            className={`hidden md:flex items-center justify-between px-2 py-1.5 mb-2 text-[11px] font-mono uppercase text-slate-500 tracking-wider ${
              isCollapsed ? 'justify-center' : ''
            }`}
          >
            {!isCollapsed && <span>Navigation</span>}
            <Terminal size={13} className="text-slate-500" />
          </div>

          <nav className="space-y-1">
            {navItems.map((item, index) => {
              const Icon = item.icon;
              const isSelected = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  id={`nav-item-${item.id.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
                  type="button"
                  onClick={() => handleTabClick(item.id)}
                  title={isCollapsed ? item.label : undefined}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded text-xs font-medium transition-colors ${
                    isCollapsed ? 'justify-center' : 'justify-between'
                  } ${
                    isSelected
                      ? 'bg-slate-800/90 text-slate-100 border border-slate-700/80 shadow-xs'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/70 border border-transparent'
                  }`}
                >
                  <div className="flex min-w-0 items-center gap-3">
                    {!isCollapsed && (
                      <span className="w-4 text-[10px] font-mono text-slate-600">{index + 1}.</span>
                    )}
                    <Icon size={17} className={isSelected ? 'text-emerald-400' : 'text-slate-400'} />
                    {!isCollapsed && <span className="truncate">{item.label}</span>}
                  </div>
                  {!isCollapsed && item.badge !== undefined && (
                    <span
                      className={`font-mono text-[10px] px-1.5 py-0.5 rounded-sm ${
                        isSelected
                          ? 'bg-emerald-950/70 text-emerald-300 border border-emerald-800/50'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="p-3 border-t border-slate-800/80 space-y-2">
          {!isCollapsed && (
            <div className="px-2 py-1.5 rounded bg-slate-900/50 border border-slate-800/50 text-[10px] font-mono text-slate-400">
              Demo trading workspace
            </div>
          )}
          <button
            id="btn-collapse-sidebar"
            type="button"
            onClick={onToggleCollapse}
            className="hidden md:flex w-full items-center justify-center p-2 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-slate-800/60 transition-colors"
            title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isCollapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
          </button>
        </div>
      </aside>
    </>
  );
};
