import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Minus, Plus, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import {
  searchProducts,
  createRequest,
  listRequests,
  deleteRequest,
  markDone,
  type Product,
  type RequestOut,
} from "@/lib/api";

function formatRelativeTime(dateStr: string): string {
  const diffMs = Date.now() - new Date(dateStr).getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  const diffHours = Math.floor(diffMs / 3_600_000);
  const diffDays = Math.floor(diffMs / 86_400_000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) {
    const time = new Date(dateStr).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
    return `yesterday at ${time}`;
  }
  return `${diffDays} days ago`;
}

export default function ManagerScreen() {
  // Section A state
  const [inputValue, setInputValue] = useState("");
  const [suggestions, setSuggestions] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [customText, setCustomText] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Section B state
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

  // Debounced product search
  useEffect(() => {
    if (!inputValue.trim() || selectedProduct !== null || customText !== null) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const results = await searchProducts(inputValue);
        setSuggestions(results.slice(0, 5));
      } catch {
        // silent — user sees the "Add as new" fallback
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [inputValue, selectedProduct, customText]);

  function selectProduct(product: Product) {
    setSelectedProduct(product);
    setCustomText(null);
    setSuggestions([]);
  }

  function selectCustom() {
    setCustomText(inputValue.trim());
    setSelectedProduct(null);
    setSuggestions([]);
  }

  function clearSelection() {
    setSelectedProduct(null);
    setCustomText(null);
    setInputValue("");
    setSuggestions([]);
  }

  async function handleAddToList() {
    if (!selectedProduct && !customText) return;
    const name = selectedProduct?.name ?? customText!;
    setIsSubmitting(true);
    try {
      if (selectedProduct) {
        await createRequest({ product_id: selectedProduct.id, quantity });
      } else {
        await createRequest({
          custom_product_name: customText!.trim(),
          quantity,
        });
      }
      toast.success(`Added ${quantity}× ${name} to the list`);
      clearSelection();
      setQuantity(1);
      await fetchPending();
    } catch {
      toast.error("Couldn't add. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteRequest(id);
      toast.success("Removed");
      setPendingRequests((prev) => prev.filter((r) => r.id !== id));
      setCheckedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } catch {
      toast.error("Couldn't remove. Try again.");
    }
  }

  function toggleCheck(id: number, checked: boolean) {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      checked ? next.add(id) : next.delete(id);
      return next;
    });
  }

  function handleSelectAll() {
    const allSelected =
      pendingRequests.length > 0 &&
      checkedIds.size === pendingRequests.length;
    setCheckedIds(
      allSelected ? new Set() : new Set(pendingRequests.map((r) => r.id))
    );
  }

  async function handleMarkDone() {
    const ids = Array.from(checkedIds);
    const count = ids.length;
    try {
      await markDone(ids);
      toast.success(`Marked ${count} as received`);
      setShowConfirmDialog(false);
      setCheckedIds(new Set());
      await fetchPending();
    } catch {
      toast.error("Couldn't mark as received. Try again.");
    }
  }

  const isSelected = selectedProduct !== null || customText !== null;
  const selectedName = selectedProduct?.name ?? customText ?? "";
  const showSuggestions =
    inputValue.trim().length > 0 && !isSelected;

  return (
    <main className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-6">
      {/* Section A — What do you need? */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-semibold">
            What do you need?
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="search-input">Search or type</Label>
            <Input
              id="search-input"
              placeholder="iPhone case, screen protector, ..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              disabled={isSelected}
              autoComplete="off"
            />
          </div>

          {/* Suggestion panel */}
          {showSuggestions && (
            <div className="rounded-lg border divide-y overflow-hidden">
              {suggestions.map((product) => (
                <button
                  key={product.id}
                  type="button"
                  onClick={() => selectProduct(product)}
                  className="w-full flex items-center justify-between gap-3 px-3 py-3 text-sm text-left hover:bg-muted transition-colors min-h-[44px]"
                >
                  <span className="truncate">{product.name}</span>
                  <Badge
                    variant="secondary"
                    className="shrink-0 capitalize text-xs"
                  >
                    {product.category.replace("_", " ")}
                  </Badge>
                </button>
              ))}
              <button
                type="button"
                onClick={selectCustom}
                className="w-full flex items-center px-3 py-3 text-sm text-left hover:bg-muted transition-colors text-muted-foreground min-h-[44px]"
              >
                + Add as new: &ldquo;{inputValue.trim()}&rdquo;
              </button>
            </div>
          )}

          {/* Selected indicator */}
          {isSelected && (
            <div className="flex items-center justify-between rounded-lg bg-muted px-3 py-2.5 text-sm">
              <span className="text-muted-foreground">
                Selected:{" "}
                <span className="text-foreground font-medium">
                  {selectedName}
                </span>
              </span>
              <button
                type="button"
                onClick={clearSelection}
                className="ml-2 shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                aria-label="Clear selection"
              >
                <X className="size-4" />
              </button>
            </div>
          )}

          {/* Quantity stepper */}
          <div className="flex items-center justify-center gap-6">
            <button
              type="button"
              onClick={() => setQuantity((q) => Math.max(1, q - 1))}
              className="flex items-center justify-center h-11 w-11 rounded-lg border border-input hover:bg-muted transition-colors"
              aria-label="Decrease quantity"
            >
              <Minus className="size-4" />
            </button>
            <span className="text-3xl font-semibold w-12 text-center tabular-nums select-none">
              {quantity}
            </span>
            <button
              type="button"
              onClick={() => setQuantity((q) => q + 1)}
              className="flex items-center justify-center h-11 w-11 rounded-lg border border-input hover:bg-muted transition-colors"
              aria-label="Increase quantity"
            >
              <Plus className="size-4" />
            </button>
          </div>

          <Button
            className="w-full h-11 text-base"
            disabled={!isSelected || isSubmitting}
            onClick={handleAddToList}
          >
            {isSubmitting ? "Adding…" : "Add to list"}
          </Button>
        </CardContent>
      </Card>

      {/* Section B — Pending pickup */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-semibold">
            Pending pickup ({pendingRequests.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {pendingRequests.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              Nothing pending. Add a request above.
            </p>
          ) : (
            <>
              <ul className="space-y-0.5">
                {pendingRequests.map((req) => {
                  const name =
                    req.product?.name ?? req.custom_product_name ?? "Unknown";
                  const label = `${req.quantity}× ${name}`;
                  const isOld =
                    Date.now() - new Date(req.created_at).getTime() >
                    24 * 60 * 60 * 1000;

                  return (
                    <li
                      key={req.id}
                      className="flex items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-muted/50 min-h-[44px]"
                    >
                      <Checkbox
                        checked={checkedIds.has(req.id)}
                        onCheckedChange={(checked) =>
                          toggleCheck(req.id, !!checked)
                        }
                        aria-label={`Select ${label}`}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium">{label}</span>
                          {isOld && (
                            <Badge
                              variant="secondary"
                              className="text-xs shrink-0"
                            >
                              from yesterday
                            </Badge>
                          )}
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {formatRelativeTime(req.created_at)}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDelete(req.id)}
                        className="ml-auto shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                        aria-label={`Remove ${label}`}
                      >
                        <X className="size-4" />
                      </button>
                    </li>
                  );
                })}
              </ul>

              <div className="flex items-center justify-between pt-3 border-t">
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
                  disabled={checkedIds.size === 0}
                  onClick={() => setShowConfirmDialog(true)}
                >
                  Mark received
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Mark-done confirmation */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Mark {checkedIds.size} item
              {checkedIds.size === 1 ? "" : "s"} as received?
            </DialogTitle>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setShowConfirmDialog(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleMarkDone}>Confirm</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
