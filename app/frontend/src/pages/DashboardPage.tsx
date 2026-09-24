import React from 'react';
import { Bell, X } from 'lucide-react';
import { ChartPanel } from '../features/chart/ChartPanel';
import { EquityCurveCard } from '../features/performance/EquityCurveCard';
import { Header } from '../components/Header';
import { PerformanceCards } from '../components/PerformanceCards';
import { PositionDetailModal } from '../components/PositionDetailModal';
import { SettingsView } from '../features/settings/SettingsView';
import { Sidebar } from '../components/Sidebar';
import { SignalFeed } from '../features/signals/SignalFeed';
import { ScannerPage } from '../features/scanner/ScannerPage';
import { ActiveTradeHistoryPage } from '../features/trades/ActiveTradeHistoryPage';
import { PerformanceStrategyPage } from '../features/performance/PerformanceStrategyPage';
import { AIAnalystDrawer } from '../features/ai/AIAnalystDrawer';
import { StaleDataBanner } from '../components/StaleDataBanner';
import { ReconciliationAlerts } from '../components/ReconciliationAlerts';
import { useDashboard } from '../hooks/useDashboard';

export const DashboardPage: React.FC = () => {
  const [isAIDrawerOpen, setIsAIDrawerOpen] = React.useState(false);
  const {
    currentTab,
    setCurrentTab,
    selectedSymbol,
    setSelectedSymbol,
    selectedTimeframe,
    setSelectedTimeframe,
    isSidebarCollapsed,
    toggleSidebarCollapse,
    isMobileSidebarOpen,
    openMobileSidebar,
    closeMobileSidebar,
    selectedPosition,
    setSelectedPosition,
    displayedPositions,
    displayedSignals,
    accountInfo,
    metrics,
    botBackend,
    signalsData,
    tradesData,
    performanceData,
    liveWs,
    liveTickerData,
    systemNotification,
    clearSystemNotification,
    reconData,
  } = useDashboard();

  const aiContext = {
    botStatus: botBackend.botStatus,
    metrics,
    openPositions: displayedPositions,
    recentSignals: displayedSignals,
    reconciliationStatus: reconData.data?.status,
    activeTab: currentTab,
  };

  return (
    <div className="h-screen min-h-0 overflow-hidden bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-emerald-500/20 selection:text-emerald-300">
      <Header
        accountInfo={accountInfo}
        isSidebarOpen={isMobileSidebarOpen}
        onToggleSidebar={() => (isMobileSidebarOpen ? closeMobileSidebar() : openMobileSidebar())}
        onOpenSettings={() => setCurrentTab('Settings')}
        onOpenAIAnalyst={() => setIsAIDrawerOpen(true)}
        botStatus={botBackend.botStatus}
        isStatusLoading={botBackend.isStatusLoading}
        isActionLoading={botBackend.isActionLoading}
        onToggleBot={botBackend.toggleBot}
        errorMessage={botBackend.errorMessage}
        successMessage={botBackend.successMessage}
        onClearMessage={botBackend.clearMessages}
      />

      <div className="min-h-0 flex-1 flex overflow-hidden">
        <Sidebar
          currentTab={currentTab}
          onSelectTab={setCurrentTab}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={toggleSidebarCollapse}
          isMobileOpen={isMobileSidebarOpen}
          onCloseMobile={closeMobileSidebar}
          positionsCount={displayedPositions.length}
          signalsCount={displayedSignals.length}
        />

        <main id="main-content-scroll-area" className="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain p-3 sm:p-4 md:p-5 space-y-4">
          <StaleDataBanner
            lastUpdatedDate={
              liveWs.lastEventTime && botBackend.lastChecked
                ? liveWs.lastEventTime > botBackend.lastChecked
                  ? liveWs.lastEventTime
                  : botBackend.lastChecked
                : liveWs.lastEventTime || botBackend.lastChecked
            }
            dataSourceName="Real-time bot"
            thresholdMinutes={15}
          />

          {systemNotification && (
            <div className="px-3 py-2 bg-indigo-950/60 border border-indigo-700/60 rounded flex items-center justify-between text-xs font-mono text-indigo-200 shadow-sm">
              <div className="flex items-center gap-2"><Bell size={14} className="text-indigo-400 shrink-0"/><span className="font-semibold text-indigo-300">System Event:</span><span>{systemNotification}</span></div>
              <button type="button" onClick={clearSystemNotification} aria-label="Dismiss notification" className="text-indigo-400 hover:text-indigo-100 p-0.5 rounded hover:bg-indigo-900/60"><X size={13}/></button>
            </div>
          )}

          <ReconciliationAlerts reconData={reconData} />

          {currentTab === 'Dashboard' && (
            <div className="space-y-4">
              <PerformanceCards metrics={metrics} isLoading={performanceData.isLoading} isError={performanceData.isError} errorMessage={performanceData.errorMessage} onRetry={performanceData.refetch}/>
              <div className="grid min-w-0 grid-cols-1 xl:grid-cols-12 gap-4 items-start">
                <div className="min-w-0 xl:col-span-8">
                  <ChartPanel
                    selectedSymbol={selectedSymbol}
                    onSelectSymbol={setSelectedSymbol}
                    selectedTimeframe={selectedTimeframe}
                    onSelectTimeframe={setSelectedTimeframe}
                    positions={displayedPositions}
                    signals={displayedSignals}
                    tickerData={liveTickerData}
                    isLivePrice={liveWs.connectionState === 'Connected'}
                  />
                </div>
                <div className="min-w-0 xl:col-span-4 space-y-4">
                  <EquityCurveCard points={performanceData.data?.equityCurve} metrics={performanceData.data?.metrics} isLoading={performanceData.isLoading}/>
                  <SignalFeed signals={displayedSignals} isLoading={signalsData.isLoading} isError={signalsData.isError} errorMessage={signalsData.errorMessage} isLiveStream={liveWs.connectionState === 'Connected'} onRetry={signalsData.refetch}/>
                </div>
              </div>
            </div>
          )}

          {currentTab === 'Scanner' && <ScannerPage />}

          {currentTab === 'Signals' && (
            <div className="space-y-4">
              <div className="border-b border-slate-800 pb-2">
                <h2 className="text-base font-semibold font-mono text-slate-100">Algorithmic Signals Feed</h2>
                <p className="text-xs text-slate-400 font-mono">Intraday strategy triggers with real-time status and confidence metrics</p>
              </div>
              <SignalFeed signals={displayedSignals} isLoading={signalsData.isLoading} isError={signalsData.isError} errorMessage={signalsData.errorMessage} isLiveStream={liveWs.connectionState === 'Connected'} onRetry={signalsData.refetch}/>
            </div>
          )}

          {currentTab === 'Active Trade & History' && (
            <ActiveTradeHistoryPage
              positions={displayedPositions}
              trades={tradesData.trades}
              onSelectPosition={setSelectedPosition}
              isLiveUpdates={liveWs.connectionState === 'Connected'}
              isLoading={tradesData.isLoading}
              isError={tradesData.isError}
              errorMessage={tradesData.errorMessage}
              onRetry={tradesData.refetch}
              filterResult={tradesData.filterResult}
              onFilterResultChange={tradesData.setFilterResult}
              filterSymbol={tradesData.filterSymbol}
              onFilterSymbolChange={tradesData.setFilterSymbol}
              filterStrategy={tradesData.filterStrategy}
              onFilterStrategyChange={tradesData.setFilterStrategy}
              onResetFilters={tradesData.resetFilters}
              hasActiveFilters={tradesData.hasActiveFilters}
            />
          )}

          {currentTab === 'Performance & Strategy' && (
            <PerformanceStrategyPage
              metrics={metrics}
              data={performanceData.data}
              isLoading={performanceData.isLoading}
              isError={performanceData.isError}
              errorMessage={performanceData.errorMessage}
              onRetry={performanceData.refetch}
              onOpenAIAnalyst={() => setIsAIDrawerOpen(true)}
            />
          )}

          {currentTab === 'Settings' && (
            <SettingsView
              backendStatus={botBackend.connectionStatus}
              websocketStatus={liveWs.connectionState}
              reconciliationStatus={reconData.data?.status}
            />
          )}
        </main>
      </div>

      <PositionDetailModal position={selectedPosition} isOpen={selectedPosition !== null} onClose={() => setSelectedPosition(null)}/>
      <AIAnalystDrawer isOpen={isAIDrawerOpen} onClose={() => setIsAIDrawerOpen(false)} contextData={aiContext} />
    </div>
  );
};
