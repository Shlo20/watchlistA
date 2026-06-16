import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { Search, Flag, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  const [pickerProductId, setPickerProductId] = useState<number | null>(null);
  const [addingIds, setAddingIds] = useState<Set<number>>(new Set());
  const pickerRef = useRef<HTMLDivElement>(null);

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

  // Close picker when clicking outside
  useEffect(() => {
    if (!pickerProductId) return;
    function handleClick(e: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setPickerProductId(null);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [pickerProductId]);

  const targetList = lists.find((l) => l.id === targetListId) ?? null;

  async function doAdd(product: Product, list: WatchList) {
    if (addingIds.has(product.id)) return;
    setAddingIds((prev) => new Set(prev).add(product.id));
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
      setAddingIds((prev) => { const s = new Set(prev); s.delete(product.id); return s; });
    }
  }

  async function handleAdd(product: Product) {
    if (targetList) {
      setPickerProductId(null);
      await doAdd(product, targetList);
    } else {
      setPickerProductId(product.id);
    }
  }

  async function pickList(product: Product, list: WatchList) {
    setTargetListId(list.id);
    localStorage.setItem(LAST_LIST_KEY, String(list.id));
    setPickerProductId(null);
    // Update local lists state with the possibly-stale list
    setLists((prev) => prev.map((l) => l.id === list.id ? list : l));
    await doAdd(product, list);
  }

  async function pickNewList(product: Product) {
    setPickerProductId(null);
    try {
      const newList = await createList({ items: [] });
      setLists((prev) => [newList, ...prev]);
      setTargetListId(newList.id);
      localStorage.setItem(LAST_LIST_KEY, String(newList.id));
      await addListItem(newList.id, { product_id: product.id, quantity: 1 });
      toast.success(`Added to "${newList.title}"`);
    } catch {
      toast.error("Couldn't create list. Try again.");
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

  return (
    <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-4">
      <h2 className="text-xl font-semibold">Search products</h2>

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

      {targetList && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>
            Adding to:{" "}
            <span className="font-medium text-foreground">{targetList.title}</span>
          </span>
          <button
            type="button"
            onClick={() => setPickerProductId(-1)}
            className="underline hover:text-foreground transition-colors"
          >
            change
          </button>
        </div>
      )}

      {/* Global list picker (opened from "change" link) */}
      {pickerProductId === -1 && (
        <div ref={pickerRef} className="rounded-lg border bg-popover shadow-md overflow-hidden">
          <p className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide border-b">
            Select target list
          </p>
          {lists.length === 0 ? (
            <p className="px-3 py-3 text-sm text-muted-foreground">No lists yet.</p>
          ) : (
            <ul className="divide-y max-h-52 overflow-y-auto">
              {lists.map((l) => (
                <li key={l.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setTargetListId(l.id);
                      localStorage.setItem(LAST_LIST_KEY, String(l.id));
                      setPickerProductId(null);
                    }}
                    className={cn(
                      "w-full flex items-center gap-2 px-3 py-3 text-sm text-left hover:bg-muted transition-colors",
                      targetListId === l.id && "bg-primary/10 text-primary font-medium"
                    )}
                  >
                    {l.title}
                    {l.has_been_sent && (
                      <Badge variant="secondary" className="ml-auto text-xs">Sent</Badge>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {query.trim() && results.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-8">No products found.</p>
      )}

      {results.length > 0 && (
        <div className="rounded-lg border divide-y overflow-hidden">
          {results.map((product) => (
            <div key={product.id} className="relative">
              <div className="flex items-center gap-2 px-3 py-3 min-h-[52px]">
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

                <div className="flex items-stretch shrink-0">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={addingIds.has(product.id)}
                    onClick={() => handleAdd(product)}
                    className="rounded-r-none border-r-0 h-8 text-xs px-3"
                  >
                    {addingIds.has(product.id) ? "Adding…" : targetList ? "Add" : "Add to list"}
                  </Button>
                  <button
                    type="button"
                    disabled={addingIds.has(product.id)}
                    onClick={() => setPickerProductId(pickerProductId === product.id ? null : product.id)}
                    className="h-8 px-1.5 rounded-r-md border border-input text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
                    aria-label="Choose list"
                  >
                    <ChevronDown className="size-3" />
                  </button>
                </div>
              </div>

              {/* Inline list picker for this product */}
              {pickerProductId === product.id && (
                <div ref={pickerRef} className="border-t bg-popover shadow-inner">
                  <p className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide border-b">
                    Add to list
                  </p>
                  {lists.length === 0 ? null : (
                    <ul className="divide-y max-h-44 overflow-y-auto">
                      {lists.map((l) => (
                        <li key={l.id}>
                          <button
                            type="button"
                            onClick={() => pickList(product, l)}
                            className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-left hover:bg-muted transition-colors"
                          >
                            {l.title}
                            {l.has_been_sent && (
                              <Badge variant="secondary" className="ml-auto text-xs">Sent</Badge>
                            )}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <button
                    type="button"
                    onClick={() => pickNewList(product)}
                    className="w-full flex items-center px-3 py-2.5 text-sm text-left hover:bg-muted transition-colors text-primary border-t"
                  >
                    + New list
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {!query.trim() && (
        <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
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
