import { useState, useEffect } from "react";
import { toast } from "sonner";
import { CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { listRequests, markDone, type RequestOut } from "@/lib/api";

export default function BuyerScreen() {
  const [pendingRequests, setPendingRequests] = useState<RequestOut[]>([]);
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  async function fetchPending() {
    try {
      const data = await listRequests({ status: "pending" });
      setPendingRequests(data);
    } catch {
      toast.error("Couldn't reach server. Check your connection.");
    }
  }

  useEffect(() => {
    fetchPending();
  }, []);

  function toggleCheck(id: number) {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function handleSelectAll() {
    const allSelected =
      pendingRequests.length > 0 && checkedIds.size === pendingRequests.length;
    setCheckedIds(
      allSelected ? new Set() : new Set(pendingRequests.map((r) => r.id))
    );
  }

  async function handleMarkDone() {
    const ids = Array.from(checkedIds);
    const count = ids.length;
    try {
      await markDone(ids);
      toast.success(`Marked ${count} item${count === 1 ? "" : "s"} done`);
      setShowConfirmDialog(false);
      setCheckedIds(new Set());
      await fetchPending();
    } catch {
      toast.error("Couldn't update. Try again.");
    }
  }

  const n = pendingRequests.length;
  const subtitle =
    n === 0
      ? "Nothing to grab right now"
      : `${n} item${n === 1 ? "" : "s"} to pick up`;

  return (
    <main className="px-4 py-8 mx-auto w-full max-w-[32rem]">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-2xl font-semibold">
            Today's restock list
          </CardTitle>
          <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>
        </CardHeader>
        <CardContent>
          {pendingRequests.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3 text-center">
              <CheckCircle2 className="size-12 text-muted-foreground" />
              <p className="text-lg font-medium">All clear!</p>
              <p className="text-sm text-muted-foreground">
                Next list arrives tomorrow morning.
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              <ul className="space-y-0.5">
                {pendingRequests.map((req) => {
                  const productName =
                    req.product?.name ?? req.custom_product_name ?? "Item";
                  const label = `${req.quantity}× ${productName}`;
                  const isOld =
                    Date.now() - new Date(req.created_at).getTime() >
                    24 * 60 * 60 * 1000;

                  return (
                    <li key={req.id}>
                      <button
                        type="button"
                        onClick={() => toggleCheck(req.id)}
                        className="w-full flex items-center gap-4 rounded-lg px-3 min-h-[48px] hover:bg-muted/60 transition-colors text-left"
                        aria-label={`Toggle ${label}`}
                      >
                        <Checkbox
                          checked={checkedIds.has(req.id)}
                          onCheckedChange={() => toggleCheck(req.id)}
                          aria-hidden
                          tabIndex={-1}
                          onClick={(e) => e.stopPropagation()}
                        />
                        <div className="flex items-center gap-2 flex-wrap flex-1 min-w-0">
                          <span className="text-base font-medium leading-snug">
                            {label}
                          </span>
                          {isOld && (
                            <Badge
                              variant="secondary"
                              className="text-xs shrink-0"
                            >
                              from yesterday
                            </Badge>
                          )}
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>

              <div className="flex items-center justify-between border-t pt-4 mt-2">
                <button
                  type="button"
                  onClick={handleSelectAll}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {checkedIds.size === pendingRequests.length
                    ? "Deselect all"
                    : "Select all"}
                </button>
                <Button
                  className="h-12 px-6 text-base font-semibold"
                  disabled={checkedIds.size === 0}
                  onClick={() => setShowConfirmDialog(true)}
                >
                  Got everything
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Confirm: Mark {checkedIds.size} item
              {checkedIds.size === 1 ? "" : "s"} as got?
            </DialogTitle>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setShowConfirmDialog(false)}
            >
              Wait, let me check
            </Button>
            <Button onClick={handleMarkDone}>Yes, all done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
