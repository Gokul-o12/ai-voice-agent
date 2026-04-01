import { useQuery } from "@tanstack/react-query";
import { getAuditTrail } from "@/lib/api";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export default function AuditTrail() {
  const { data: records, isLoading } = useQuery({
    queryKey: ["auditTrail"],
    queryFn: getAuditTrail,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  if (isLoading) return <div className="text-sm text-muted-foreground mt-8">Loading Audit Trail...</div>;

  return (
    <div className="mt-12">
      <h2 className="text-2xl font-bold tracking-tight mb-4">Call Intelligence Logs</h2>
      <div className="rounded-md border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Line</TableHead>
              <TableHead>Supervisor</TableHead>
              <TableHead>Sentiment</TableHead>
              <TableHead>Issues</TableHead>
              <TableHead className="text-right">Transcript</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {records?.map((record) => (
              <TableRow key={record.call_id}>
                <TableCell className="font-medium text-xs">
                  {new Date(record.start_time).toLocaleString()}
                </TableCell>
                <TableCell>{record.line_id}</TableCell>
                <TableCell>{record.supervisor}</TableCell>
                <TableCell>
                  {/* Color-code the sentiment */}
                  <Badge variant={record.sentiment === "positive" ? "default" : record.sentiment === "negative" ? "destructive" : "secondary"}>
                    {record.sentiment.toUpperCase()}
                  </Badge>
                </TableCell>
                <TableCell>
                  {record.unresolved_issues.length > 0 ? (
                     <span className="text-red-500 font-bold">{record.unresolved_issues.length} Flagged</span>
                  ) : "None"}
                </TableCell>
                <TableCell className="text-right">
                  
                  {/* 🌟 The Modal to view the chat transcript */}
                  <Dialog>
                    <DialogTrigger asChild>
                      <Button variant="outline" size="sm">View</Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                      <DialogHeader>
                        <DialogTitle>Call Transcript: {record.supervisor} ({record.line_id})</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4 mt-4">
                        {record.transcript.length === 0 ? (
  <div className="bg-amber-50 border border-amber-200 text-amber-800 p-4 rounded-md flex items-center gap-3">
    <span className="text-xl">⚠️</span>
    <div>
      <h4 className="font-semibold">Call Abandoned</h4>
      <p className="text-sm opacity-90">The supervisor hung up early, or the call timed out due to 30 seconds of silence. The Auto-Pilot will try calling them again later.</p>
    </div>
  </div>
) : null}
                        {record.transcript.map((turn, i) => (
                          <div key={i} className="flex flex-col gap-2 text-sm">
                            <div className="bg-primary/10 p-3 rounded-lg mr-12 text-primary">
                              <strong>AI:</strong> {turn.ai}
                            </div>
                            <div className="bg-muted p-3 rounded-lg ml-12 text-foreground">
                              <strong>Supervisor:</strong> {turn.user}
                            </div>
                          </div>
                        ))}
                      </div>
                    </DialogContent>
                  </Dialog>

                </TableCell>
              </TableRow>
            ))}
            {records?.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  No calls recorded yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}