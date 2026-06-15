import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Inbox, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  getInbox,
  updateSendItem,
  markAllReceived,
  dismissSend,
  clearInbox,
  type InboxSend,
  type SendItemState,
} from "@/lib/api";

type DateGroup = "Today" | "Yesterday" | "This Week" | "Earlier";

function getDateGroup(dateStr: string): DateGroup {
  const diffDays = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86_400_000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return "This Week";
  return "Earlier";
}

function groupSends(sends: InboxSend[]): Array<{ label: DateGroup; sends: InboxSend[] }> {
  const groups: Record<DateGroup, InboxSend[]> = {
    Today: [],
    Yesterday: [],
    "This Week": [],
    Earlier: [],
  };
  for (const s of sends) {
    groups[getDateGroup(s.created_at)].push(s);
  }
  const order: DateGroup[] = ["Today", "Yesterday", "This Week", "Earlier"];
  return order
    .filter((g) => groups[g].length > 0)
    .map((g) => ({ label: g, sends: groups[g] }));
}

function getItemState(itemStates: SendItemState[], listItemId: number): SendItemState {
  return (
    itemStates.find((s) => s.list_item_id === listItemId) ?? {
      list_item_id: listItemId,
      checked: false,
      received_quantity: 0,
    }
  );
}

function applyCheck(send: InboxSend, listItemId: number, checked: boolean): InboxSend {
  const itemStates = send.item_states ?? [];
  const exists = itemStates.some((s) => s.list_item_id === listItemId);
  return {
    ...send,
    item_states: exists
      ? itemStates.map((s) => (s.list_item_id === listItemId ? { ...s, checked } : s))
      : [...itemStates, { list_item_id: listItemId, checked, received_quantity: 0 }],
  };
}

export default function InboxSection() {
  const [sends, setSends] = useState<InboxSend[]>([]);
  const [loading, setLoading] = useState(true);
  const [dismissingIds, setDismissingIds] = useState<Set<number>>(new Set());
  const [clearConfirming, setClearConfirming] = useState(false);
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    getInbox()
      .then(setSends)
      .catch(() => toast.error("Couldn't load inbox."))
      .finally(() => setLoading(false));
  }, []);

  async function handleToggle(sendId: number, listItemId: number, newChecked: boolean) {
    setSends((prev) =>
      prev.map((s) => (s.id === sendId ? applyCheck(s, listItemId, newChecked) : s))
    );
    try {
      await updateSendItem(sendId, listItemId, { checked: newChecked });
    } catch {
      setSends((prev) =>
        prev.map((s) => (s.id === sendId ? applyCheck(s, listItemId, !newChecked) : s))
      );
      toast.error("Couldn't update. Try again.");
    }
  }

  async function handleMarkAll(sendId: number) {
    try {
      const updated = await markAllReceived(sendId);
      setSends((prev) => prev.map((s) => (s.id === sendId ? updated : s)));
      toast.success("All items marked received");
    } catch {
      toast.error("Couldn't update. Try again.");
    }
  }

  async function handleDismiss(sendId: number) {
    setDismissingIds((prev) => new Set(prev).add(sendId));
    try {
      await dismissSend(sendId);
      setTimeout(() => {
        setSends((prev) => prev.filter((s) => s.id !== sendId));
        setDismissingIds((prev) => {
          const next = new Set(prev);
          next.delete(sendId);
          return next;
        });
      }, 200);
    } catch {
      setDismissingIds((prev) => {
        const next = new Set(prev);
        next.delete(sendId);
        return next;
      });
      toast.error("Couldn't dismiss. Try again.");
    }
  }

  async function handleClearInbox() {
    setClearing(true);
    try {
      await clearInbox();
      setSends([]);
      setClearConfirming(false);
      toast.success("Inbox cleared");
    } catch {
      toast.error("Couldn't clear inbox. Try again.");
    } finally {
      setClearing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (sends.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-4">
        <Inbox className="size-12 text-muted-foreground" />
        <p className="text-lg font-medium">Inbox is clear</p>
        <p className="text-sm text-muted-foreground">Lists sent to you will appear here.</p>
      </div>
    );
  }

  const groups = groupSends(sends);

  return (
    <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Inbox</h2>
        {clearConfirming ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Clear all?</span>
            <Button
              size="sm"
              variant="destructive"
              onClick={handleClearInbox}
              disabled={clearing}
              className="h-8 text-xs"
            >
              {clearing ? "Clearing…" : "Yes, clear"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setClearConfirming(false)}
              className="h-8 text-xs"
            >
              Cancel
            </Button>
          </div>
        ) : (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setClearConfirming(true)}
            className="h-8 text-xs text-muted-foreground hover:text-foreground"
          >
            Clear inbox
          </Button>
        )}
      </div>

      {/* Date groups */}
      {groups.map(({ label, sends: groupSends }) => (
        <section key={label} className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-1">
            {label}
          </h3>

          {groupSends.map((send) => {
            const items = send.items ?? [];
            const itemStates = send.item_states ?? [];
            const checkedCount = itemStates.filter((s) => s.checked).length;
            const total = items.length;
            const progress = total > 0 ? (checkedCount / total) * 100 : 0;
            const allDone = total > 0 && checkedCount === total;
            const dismissing = dismissingIds.has(send.id);

            return (
              <div
                key={send.id}
                className={[
                  "transition-all duration-150",
                  dismissing
                    ? "opacity-0 scale-95 pointer-events-none"
                    : "opacity-100 scale-100",
                ].join(" ")}
              >
                <Card>
                  <CardHeader className="pb-2">
                    <div className="flex items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <CardTitle className="text-base truncate">
                          {send.list_title ?? "Restock list"}
                        </CardTitle>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {send.sender_name ? `From ${send.sender_name}` : "Received list"}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0 mt-0.5">
                        <Badge variant={allDone ? "default" : "secondary"} className="text-xs">
                          {checkedCount}/{total}
                        </Badge>
                        <button
                          type="button"
                          onClick={() => handleDismiss(send.id)}
                          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors flex items-center justify-center min-w-[32px] min-h-[32px]"
                          aria-label="Dismiss"
                        >
                          <X className="size-3.5" />
                        </button>
                      </div>
                    </div>
                    {/* Progress bar */}
                    <div className="h-1 bg-muted rounded-full mt-2 overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all duration-300"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </CardHeader>

                  <CardContent className="pt-0 pb-3">
                    {items.length === 0 ? (
                      <p className="text-sm text-muted-foreground py-2">No items.</p>
                    ) : (
                      <>
                        <ul className="space-y-0.5">
                          {items.map((item) => {
                            const state = getItemState(itemStates, item.id);
                            const name =
                              item.product_name ?? item.custom_product_name ?? "Item";
                            const label = `${item.quantity}× ${name}`;
                            return (
                              <li key={item.id}>
                                <button
                                  type="button"
                                  onClick={() =>
                                    handleToggle(send.id, item.id, !state.checked)
                                  }
                                  className="w-full flex items-center gap-3 rounded-lg px-3 min-h-[44px] hover:bg-muted/60 transition-colors text-left"
                                  aria-label={`Toggle ${label}`}
                                >
                                  <Checkbox
                                    checked={state.checked}
                                    onCheckedChange={(checked) =>
                                      handleToggle(send.id, item.id, !!checked)
                                    }
                                    aria-hidden
                                    tabIndex={-1}
                                    onClick={(e) => e.stopPropagation()}
                                  />
                                  <span
                                    className={[
                                      "text-sm font-medium transition-colors",
                                      state.checked
                                        ? "line-through text-muted-foreground"
                                        : "",
                                    ].join(" ")}
                                  >
                                    {label}
                                  </span>
                                </button>
                              </li>
                            );
                          })}
                        </ul>
                        {!allDone && (
                          <div className="pt-2 border-t border-border/50 mt-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleMarkAll(send.id)}
                              className="h-8 text-xs text-muted-foreground hover:text-foreground w-full"
                            >
                              Mark all received
                            </Button>
                          </div>
                        )}
                      </>
                    )}
                  </CardContent>
                </Card>
              </div>
            );
          })}
        </section>
      ))}
    </div>
  );
}
