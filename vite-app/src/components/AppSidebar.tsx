import { Factory, LayoutDashboard, CalendarPlus } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";

// Define the props so we can pass our activePage state from App.tsx
interface AppSidebarProps {
  activePage: "dashboard" | "scheduler";
  setActivePage: (page: "dashboard" | "scheduler") => void;
}

export function AppSidebar({ activePage, setActivePage }: AppSidebarProps) {
  return (
    <Sidebar>
      {/* Brand Header */}
      <SidebarHeader className="border-b px-6 py-5">
        <div className="flex items-center gap-3">
          <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Factory className="size-5" />
          </div>
          <div className="flex flex-col gap-0.5 leading-none">
            <span className="font-semibold text-base">Voice Workforce</span>
            <span className="text-xs text-muted-foreground">v4 Enterprise</span>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        {/* Main Navigation Group */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-xs font-medium text-muted-foreground mt-4 mb-2 px-4 uppercase tracking-wider">
            Factory Floor
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              
              <SidebarMenuItem>
                <SidebarMenuButton 
                  isActive={activePage === "dashboard"}
                  onClick={() => setActivePage("dashboard")}
                  className="px-4 py-6 text-sm transition-all"
                >
                  <LayoutDashboard className="mr-2 size-5" />
                  <span>Command Center</span>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton 
                  isActive={activePage === "scheduler"}
                  onClick={() => setActivePage("scheduler")}
                  className="px-4 py-6 text-sm transition-all"
                >
                  <CalendarPlus className="mr-2 size-5" />
                  <span>Line Scheduler</span>
                </SidebarMenuButton>
              </SidebarMenuItem>

            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarRail />
    </Sidebar>
  );
}