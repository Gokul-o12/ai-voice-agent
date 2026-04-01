import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
// import { uploadSchedule, DailySchedule } from "@/lib/api";
import { uploadSchedule, type DailySchedule } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export default function Scheduler() {
  const queryClient = useQueryClient();
  
  // Form State
  const [lineId, setLineId] = useState("");
  const [supervisorName, setSupervisorName] = useState("");
  const [supervisorPhone, setSupervisorPhone] = useState("");
  const [orders, setOrders] = useState([{ order_sequence: 1, order_name: "" }]);

  // React Query Mutation to handle the POST request
  const mutation = useMutation({
    mutationFn: uploadSchedule,
    onSuccess: () => {
      alert("✅ Schedule successfully uploaded!");
      // Reset form
      setLineId("");
      setSupervisorName("");
      setSupervisorPhone("");
      setOrders([{ order_sequence: 1, order_name: "" }]);
      // Instantly refresh the Command Center data!
      queryClient.invalidateQueries({ queryKey: ["factoryStatus"] });
    },
    onError: (error) => {
      alert("❌ Failed to upload schedule: " + error.message);
    }
  });

  const handleAddOrder = () => {
    setOrders([...orders, { order_sequence: orders.length + 1, order_name: "" }]);
  };

  const handleOrderChange = (index: number, value: string) => {
    const newOrders = [...orders];
    newOrders[index].order_name = value;
    setOrders(newOrders);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Build the payload
    const payload: DailySchedule = {
      line_id: lineId,
      supervisor_name: supervisorName,
      supervisor_phone: supervisorPhone,
      // Filter out any blank orders just in case
      orders: orders.filter(o => o.order_name.trim() !== "")
    };

    mutation.mutate(payload);
  };

  return (
    <Card className="mt-8">
      <CardHeader>
        <CardTitle>Daily Line Scheduler</CardTitle>
        <CardDescription>Assign a supervisor and upload the daily sequence of orders.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          
          {/* Top Row: Line & Supervisor Details */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="lineId">Line ID</Label>
              <Input id="lineId" value={lineId} onChange={(e) => setLineId(e.target.value)} placeholder="e.g. Line-Charlie" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="supervisorName">Supervisor Name</Label>
              <Input id="supervisorName" value={supervisorName} onChange={(e) => setSupervisorName(e.target.value)} placeholder="e.g. Sarah" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Phone Number</Label>
              <Input id="phone" value={supervisorPhone} onChange={(e) => setSupervisorPhone(e.target.value)} placeholder="+1234567890" required />
            </div>
          </div>

          {/* Bottom Section: Dynamic Orders */}
          <div className="space-y-4">
            <Label>Production Orders Sequence</Label>
            {orders.map((order, index) => (
              <div key={index} className="flex items-center gap-4">
                <div className="bg-muted px-3 py-2 rounded-md text-sm font-bold text-muted-foreground">
                  Order {order.order_sequence}
                </div>
                <Input 
                  value={order.order_name} 
                  onChange={(e) => handleOrderChange(index, e.target.value)} 
                  placeholder="e.g. Assemble Chassis" 
                  required 
                />
              </div>
            ))}
            
            <Button type="button" variant="outline" size="sm" onClick={handleAddOrder}>
              + Add Another Order
            </Button>
          </div>

          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? "Uploading..." : "Publish Schedule to Factory Floor"}
          </Button>

        </form>
      </CardContent>
    </Card>
  );
}