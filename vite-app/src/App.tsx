import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppSidebar } from "./components/AppSidebar";
import CommandCenter from "./components/CommandCenter";
import AuditTrail from "./components/AuditTrail";
import Scheduler from "./components/Scheduler";
import { 
  SidebarProvider, 
  SidebarInset, 
  SidebarTrigger 
} from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb";

// Initialize the Query Client
const queryClient = new QueryClient();

export default function App() {
  const [activePage, setActivePage] = useState<"dashboard" | "scheduler">("dashboard");

  return (
    <QueryClientProvider client={queryClient}>
      {/* 🌟 NEW: The SidebarProvider wraps the entire app */}
      <SidebarProvider>
        
        {/* The Sidebar Component we just created */}
        <AppSidebar activePage={activePage} setActivePage={setActivePage} />
        
        {/* 🌟 NEW: SidebarInset is the main content area */}
        <SidebarInset className="bg-muted/20 min-h-screen">
          
          {/* Sticky Header with Collapse Trigger and Breadcrumbs */}
          <header className="flex h-16 shrink-0 items-center gap-2 border-b bg-background px-4 sticky top-0 z-10">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbPage className="font-medium">
                    {activePage === "dashboard" ? "Command Center" : "Line Scheduler"}
                  </BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </header>

          {/* Page Content Engine */}
          <main className="p-8 max-w-7xl w-full mx-auto space-y-8 animate-in fade-in duration-500">
            
            {/* PAGE 1: THE DASHBOARD */}
            {activePage === "dashboard" && (
              <div className="space-y-8">
                <header>
                  <h2 className="text-3xl font-bold tracking-tight">Command Center</h2>
                  <p className="text-muted-foreground">Live Factory Audio & Auto-Pilot Status</p>
                </header>
                <CommandCenter />
                <AuditTrail />
              </div>
            )}

            {/* PAGE 2: THE SCHEDULER */}
            {activePage === "scheduler" && (
              <div className="space-y-8">
                <header>
                  <h2 className="text-3xl font-bold tracking-tight">Line Scheduler</h2>
                  <p className="text-muted-foreground">Assign supervisors and plan daily production orders.</p>
                </header>
                <div className="max-w-3xl">
                   <Scheduler />
                </div>
              </div>
            )}

          </main>

        </SidebarInset>
      </SidebarProvider>
    </QueryClientProvider>
  );
}