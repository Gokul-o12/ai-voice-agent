// import { useQuery } from "@tanstack/react-query";
// import { getFactoryStatus } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useQuery, useMutation } from "@tanstack/react-query"; // Add useMutation
import { getFactoryStatus, triggerManualCall } from "@/lib/api"; // Import the new API function
import { PhoneCall, AlertTriangle, CheckCircle2 } from "lucide-react"; // Let's add some icons!
import { AxiosError } from "axios";

export default function CommandCenter() {
  // 🌟 NEW: React Query handles the fetching, caching, and auto-refreshing!
  const { data: lines, isLoading, isError } = useQuery({
    queryKey: ["factoryStatus"],
    queryFn: getFactoryStatus,
    refetchInterval: 2000, // Auto-refresh every 2 seconds for that "live" feel
  });

  // 🌟 FIX: We tell TypeScript this is an AxiosError that might contain a "detail" string
  const callMutation = useMutation({
    mutationFn: triggerManualCall,
    onSuccess: (data) => {
      alert(`📞 ${data.message}`);
    },
    onError: (error: AxiosError<{ detail: string }>) => {
      alert(`❌ Failed to connect: ${error.response?.data?.detail || error.message}`);
    }
  });

  if (isLoading) {
    return <div className="text-muted-foreground animate-pulse">Connecting to Factory Floor...</div>;
  }

  if (isError || !lines) {
    return <div className="text-red-500 font-medium">⚠️ Connection to Auto-Pilot lost.</div>;
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {lines.map((line) => (
        <Card 
          key={line.id} 
          // 🌟 NEW: If Blocked, make the card border red and background slightly red!
          className={line.status === "Blocked" ? "border-red-500 bg-red-50 dark:bg-red-950/20" : ""}
        >
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium">
              {line.id}
            </CardTitle>
            
            {/* 🌟 NEW: Badge Logic */}
            {line.status === "Blocked" ? (
              <Badge variant="destructive" className="animate-pulse">BLOCKED</Badge>
            ) : line.status === "Active" ? (
              <Badge variant="default" className="bg-green-500 hover:bg-green-600">Active</Badge>
            ) : (
              <Badge variant="secondary">Idle</Badge>
            )}

          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{line.supervisor}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {line.orders} Pending Orders
            </p>
            <div className="mt-4">
  <button 
    onClick={() => callMutation.mutate(line.id)}
    disabled={callMutation.isPending || line.status === "Idle"}
    className={`w-full flex items-center justify-center gap-2 text-xs text-primary-foreground py-2.5 rounded-md transition disabled:opacity-50 ${
      line.status === "Blocked" ? "bg-red-600 hover:bg-red-700" : 
      line.status === "Active" ? "bg-primary hover:bg-primary/90" : 
      "bg-muted-foreground"
    }`}
  >
    {/* Dynamic Icons and Text based on Status */}
    {callMutation.isPending && callMutation.variables === line.id ? (
      <>Dialing Agent...</>
    ) : line.status === "Blocked" ? (
      <><AlertTriangle className="size-4" /> Resolve Blocker</>
    ) : line.status === "Active" ? (
      <><PhoneCall className="size-4" /> Monitor Line</>
    ) : (
      <><CheckCircle2 className="size-4" /> Line Completed</>
    )}
  </button>
</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}