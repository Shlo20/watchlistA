import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Inbox } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  getInbox,
  updateSendItem,
  type InboxSend,
  type SendItemState,
} from "@/lib/api";

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  const diffDays = Math.floor((Date.now() - d.getTime()) / 86_400_000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function getItemState(
  itemStates: SendItemState[],
  listItemId: number
): SendItemState {
  return (
    itemStates.find((s) => s.list_item_id === listItemId) ?? {
      list_item_id: listItemId,
      checked: false,
      received_quantity: 0,
    }
  );
}

function applyCheck(
  send: InboxSend,
  listItemId: number,
  checked: boolean
): InboxSend {
  const itemStates = send.item_states ?? [];
  const exists = itemStates.some((s) => s.list_item_id === listItemId);
  return {
    ...send,
    item_states: exists
      ? itemStates.map((s) =>
          s.list_item_id === listItemId ? { ...s, checked } : s
        )
      : [
          ...itemStates,
          { list_item_id: listItemId, checked, received_quantity: 0 },
        ],
  };
}

export default function InboxSection() {
  const [sends, setSends] = useState<InboxSend[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getInbox()
      .then(setSends)
      .catch(() => toast.error("Couldn't load inbox."))
      .finally(() => setLoading(false));
  }, []);

  async function handleToggle(
    sendId: number,
    listItemId: number,
    newChecked: boolean
  ) {
    setSends((prev) =>
      prev.map((s) =>
        s.id === sendId ? applyCheck(s, listItemId, newChecked) : s
      )
    );
    try {
      await updateSendItem(sendId, listItemId, { checked: newChecked });
    } catch {
      setSends((prev) =>
        prev.map((s) =>
          s.id === sendId ? applyCheck(s, listItemId, !newChecked) : s
        )
      );
      toast.error("Couldn't update. Try again.");
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
        <p className="text-lg font-medium">No lists received yet</p>
        <p className="text-sm text-muted-foreground">
          Lists sent to you will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-4">
      <h2 className="text-xl font-semibold">Inbox</h2>

      {sends.map((send) => {
        const items = send.items ?? [];
        const itemStates = send.item_states ?? [];
        const checkedCount = itemStates.filter((s) => s.checked).length;
        const total = items.length;
        const allDone = total > 0 && checkedCount === total;

        return (
          <Card key={send.id}>
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <CardTitle className="text-base truncate">
                    {send.list_title ?? "Restock list"}
                  </CardTitle>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {send.sender_name
                      ? `From ${send.sender_name} · ${formatDate(send.created_at)}`
                      : formatDate(send.created_at)}
                  </p>
                </div>
                <Badge
                  variant={allDone ? "default" : "secondary"}
                  className="shrink-0"
                >
                  {checkedCount}/{total} received
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              {items.length === 0 ? (
                <p className="text-sm text-muted-foreground py-2">
                  No items in this list.
                </p>
              ) : (
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
                          className="w-full flex items-center gap-4 rounded-lg px-3 min-h-[48px] hover:bg-muted/60 transition-colors text-left"
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
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
