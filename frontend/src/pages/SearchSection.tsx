import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { Search, Flag, Plus, ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  searchProducts,
  listLists,
  addListItem,
  createList,
  flagLow,
  unflagLow,
  type Product,
  type WatchList,
} from "@/lib/api";

const LAST_LIST_KEY = "watchlist_last_list_id";

export default function SearchSection() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Product[]>([]);
  const [lists, setLists] = useState<WatchList[]>([]);
  const [targetListId, setTargetListId] = useState<number | null>(() => {
    const saved = localStorage.getItem(LAST_LIST_KEY);
    return saved ? Number(saved) : null;
  });
  const [pickerOpen, setPickerOpen] = useState(false);
  const [creatingList, setCreatingList] = useState(false);
  const [addingProductIds, setAddingProductIds] = useState<Set<number>>(new Set());
  const [addingCustom, setAddingCustom] = useState(false);
  const selectorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listLists()
      .then(setLists)
      .catch(() => {});
  }, []);

  // Debounced search
  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) { setResults([]); return; }
    const timer = setTimeout(() => {
      searchProducts(trimmed)
        .then((data) => setResults(data.slice(0, 8)))
        .catch(() => {});
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  // Close picker on outside click
  useEffect(() => {
    if (!pickerOpen) return;
    function onMouseDown(e: MouseEvent) {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node)) {
        setPickerOpen(false);
      }
    }
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [pickerOpen]);

  // Drop saved target if it no longer exists in lists
  useEffect(() => {
    if (targetListId !== null && lists.length > 0 && !lists.find((l) => l.id === targetListId)) {
      setTargetListId(null);
      localStorage.removeItem(LAST_LIST_KEY);
    }
  }, [lists, targetListId]);

  const targetList = lists.find((l) => l.id === targetListId) ?? null;

  function selectList(list: WatchList) {
    setTargetListId(list.id);
    localStorage.setItem(LAST_LIST_KEY, String(list.id));
    setPickerOpen(false);
  }

  async function handleNewList() {
    setCreatingList(true);
    setPickerOpen(false);
    try {
      const created = await createList({ items: [] });
      setLists((prev) => [created, ...prev]);
      setTargetListId(created.id);
      localStorage.setItem(LAST_LIST_KEY, String(created.id));
    } catch {
      toast.error("Couldn't create list. Try again.");
    } finally {
      setCreatingList(false);
    }
  }

  // Returns the target list, opening the picker or auto-creating as needed.
  async function resolveTarget(): Promise<WatchList | null> {
    if (targetList) return targetList;
    if (lists.length > 0) {
      // Lists exist but none selected — prompt user to pick
      setPickerOpen(true);
      return null;
    }
    // No lists at all — auto-create one
    setCreatingList(true);
    try {
      const created = await createList({ items: [] });
      setLists((prev) => [created, ...prev]);
      setTargetListId(created.id);
      localStorage.setItem(LAST_LIST_KEY, String(created.id));
      return created;
    } catch {
      toast.error("Couldn't create a list. Try again.");
      return null;
    } finally {
      setCreatingList(false);
    }
  }

  async function handleAddProduct(product: Product) {
    if (addingProductIds.has(product.id)) return;
    const list = await resolveTarget();
    if (!list) return;
    setAddingProductIds((prev) => new Set(prev).add(product.id));
    try {
      await addListItem(list.id, { product_id: product.id, quantity: 1 });
      if (list.has_been_sent) {
        toast.warning(`Added to "${list.title}" — this list was already sent`);
      } else {
        toast.success(`Added to "${list.title}"`);
      }
    } catch {
      toast.error("Couldn't add item. Try again.");
    } finally {
      setAddingProductIds((prev) => { const s = new Set(prev); s.delete(product.id); return s; });
    }
  }

  async function handleAddCustom() {
    const name = query.trim();
    if (!name || addingCustom) return;
    const list = await resolveTarget();
    if (!list) return;
    setAddingCustom(true);
    try {
      await addListItem(list.id, { custom_product_name: name, quantity: 1 });
      if (list.has_been_sent) {
        toast.warning(`Added "${name}" to "${list.title}" — this list was already sent`);
      } else {
        toast.success(`Added "${name}" to "${list.title}"`);
      }
    } catch {
      toast.error("Couldn't add item. Try again.");
    } finally {
      setAddingCustom(false);
    }
  }

  async function toggleFlag(product: Product) {
    if (product.is_low) {
      await unflagLow(product.id).catch(() => toast.error("Couldn't unflag."));
      setResults((prev) => prev.map((p) => p.id === product.id ? { ...p, is_low: false } : p));
    } else {
      const updated = await flagLow(product.id).catch(() => null);
      if (updated) {
        setResults((prev) => prev.map((p) => p.id === product.id ? { ...p, is_low: true } : p));
        toast.success(`${product.name} flagged as running low`);
      }
    }
  }

  const hasQuery = query.trim().length > 0;

  return (
    <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-4">
      <h2 className="text-xl font-semibold">Search products</h2>

      {/* ── Target list selector ── */}
      <div ref={selectorRef} className="relative">
        <button
          type="button"
          onClick={() => setPickerOpen((o) => !o)}
          disabled={creatingList}
          className={cn(
            "w-full flex items-center gap-3 px-4 py-3 rounded-xl border text-sm transition-colors text-left",
            pickerOpen
              ? "border-primary bg-primary/5"
              : "border-border bg-card hover:border-muted-foreground/60"
          )}
        >
          <div className="flex-1 min-w-0 flex items-center gap-2 flex-wrap">
            {creatingList ? (
              <span className="text-muted-foreground">Creating list…</span>
            ) : targetList ? (
              <>
                <span className="text-xs text-muted-foreground shrink-0">Adding to</span>
                <span className="font-medium truncate">{targetList.title}</span>
                {targetList.has_been_sent && (
                  <Badge variant="secondary" className="text-xs shrink-0">Sent</Badge>
                )}
              </>
            ) : (
              <span className="text-muted-foreground">Select a list to add items to…</span>
            )}
          </div>
          <ChevronDown
            className={cn(
              "size-4 text-muted-foreground shrink-0 transition-transform duration-150",
              pickerOpen && "rotate-180"
            )}
          />
        </button>

        {pickerOpen && (
          <div className="absolute top-full mt-1.5 left-0 right-0 z-30 rounded-xl border bg-popover shadow-lg overflow-hidden">
            {lists.length > 0 && (
              <ul className="divide-y max-h-52 overflow-y-auto">
                {lists.map((l) => {
                  const active = l.id === targetListId;
                  return (
                    <li key={l.id}>
                      <button
                        type="button"
                        onClick={() => selectList(l)}
                        className={cn(
                          "w-full flex items-center gap-3 px-4 py-3 text-sm text-left hover:bg-muted transition-colors",
                          active && "bg-primary/8 text-primary font-medium"
                        )}
                      >
                        <Check className={cn("size-3.5 shrink-0", active ? "opacity-100" : "opacity-0")} />
                        <span className="flex-1 truncate">{l.title}</span>
                        {l.has_been_sent && (
                          <Badge variant="secondary" className="text-xs shrink-0">Sent</Badge>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            <button
              type="button"
              onClick={handleNewList}
              className={cn(
                "w-full flex items-center gap-2 px-4 py-3 text-sm text-left text-primary hover:bg-muted transition-colors",
                lists.length > 0 && "border-t"
              )}
            >
              <Plus className="size-3.5 shrink-0" />
              New list
            </button>
          </div>
        )}
      </div>

      {/* ── Search input ── */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
        <Input
          className="pl-9"
          placeholder="Search by name, SKU, category…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
      </div>

      {/* ── Results ── */}
      {hasQuery && (
        <div className="rounded-xl border divide-y overflow-hidden">
          {results.map((product) => (
            <div key={product.id} className="flex items-center gap-3 px-4 py-3.5 min-h-[56px]">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{product.name}</p>
                <Badge variant="secondary" className="capitalize text-xs mt-0.5">
                  {product.category.replace("_", " ")}
                </Badge>
              </div>

              <button
                type="button"
                onClick={() => toggleFlag(product)}
                className={cn(
                  "shrink-0 p-1.5 rounded transition-colors",
                  product.is_low
                    ? "text-amber-400 hover:text-amber-300"
                    : "text-muted-foreground hover:text-amber-400"
                )}
                aria-label={product.is_low ? "Unmark running low" : "Mark running low"}
                title={product.is_low ? "Running low — click to clear" : "Mark running low"}
              >
                <Flag className="size-3.5" />
              </button>

              <button
                type="button"
                disabled={addingProductIds.has(product.id)}
                onClick={() => handleAddProduct(product)}
                className="shrink-0 flex items-center justify-center size-8 rounded-lg border border-input text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
                aria-label={`Add ${product.name}`}
              >
                <Plus className="size-4" />
              </button>
            </div>
          ))}

          {/* Custom item row — always shown when there's a query */}
          <div className="flex items-center gap-3 px-4 py-3.5 min-h-[56px] bg-muted/25">
            <p className="flex-1 text-sm text-muted-foreground min-w-0 truncate">
              Add as custom: <span className="font-medium text-foreground">&ldquo;{query.trim()}&rdquo;</span>
            </p>
            <button
              type="button"
              disabled={addingCustom}
              onClick={handleAddCustom}
              className="shrink-0 flex items-center justify-center size-8 rounded-lg border border-input text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
              aria-label="Add as custom item"
            >
              <Plus className="size-4" />
            </button>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!hasQuery && (
        <div className="flex flex-col items-center justify-center py-12 gap-4 text-center">
          <div className="flex items-center justify-center size-16 rounded-2xl bg-muted">
            <Search className="size-7 text-primary/60" />
          </div>
          <p className="text-sm text-muted-foreground max-w-[220px]">
            Search for products to add to a list or flag as running low.
          </p>
        </div>
      )}
    </div>
  );
}
