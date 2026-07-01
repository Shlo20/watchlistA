import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { Flag, X, Plus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getLowProducts, unflagLow, createList, type Product } from "@/lib/api";

export default function LowStockSection() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const creatingRef = useRef(false);
  const unflaggingRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    getLowProducts()
      .then(setProducts)
      .catch(() => toast.error("Couldn't load low-stock items."))
      .finally(() => setLoading(false));
  }, []);

  async function handleUnflag(product: Product) {
    if (unflaggingRef.current.has(product.id)) return;
    unflaggingRef.current.add(product.id);
    try {
      await unflagLow(product.id);
      // Only remove from the UI once the server confirms — otherwise the item
      // vanishes locally while still flagged on the server.
      setProducts((prev) => prev.filter((p) => p.id !== product.id));
    } catch {
      toast.error("Couldn't unflag. Try again.");
    } finally {
      unflaggingRef.current.delete(product.id);
    }
  }

  async function handleCreateRestockList() {
    // Ref guard: a fast double-tap fires before the disabled state renders,
    // which would create two identical restock lists.
    if (products.length === 0 || creatingRef.current) return;
    creatingRef.current = true;
    setCreating(true);
    try {
      await createList({
        items: products.map((p) => ({ product_id: p.id, quantity: 1 })),
      });
      toast.success("Restock list created — find it in Lists");
    } catch {
      toast.error("Couldn't create list. Try again.");
    } finally {
      creatingRef.current = false;
      setCreating(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-5 text-center px-8">
        <div className="flex items-center justify-center size-20 rounded-2xl bg-muted">
          <Flag className="size-9 text-amber-400/70" />
        </div>
        <div className="space-y-1.5">
          <p className="text-lg font-semibold">Nothing flagged low</p>
          <p className="text-sm text-muted-foreground max-w-[240px]">
            Flag products as running low from the Search tab.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Flag className="size-5 text-amber-400" />
          Running low
        </h2>
        <Button
          size="sm"
          onClick={handleCreateRestockList}
          disabled={creating}
          className="gap-1.5"
        >
          <Plus className="size-3.5" />
          {creating ? "Creating…" : "New restock list"}
        </Button>
      </div>

      <Card>
        <CardContent className="pt-4 pb-2">
          <ul className="divide-y">
            {products.map((product) => (
              <li key={product.id} className="flex items-center gap-3 py-3 min-h-[52px]">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{product.name}</p>
                  <Badge variant="secondary" className="capitalize text-xs mt-0.5">
                    {product.category.replace("_", " ")}
                  </Badge>
                </div>
                <button
                  type="button"
                  onClick={() => handleUnflag(product)}
                  className="shrink-0 text-muted-foreground hover:text-foreground transition-colors p-1"
                  aria-label={`Unflag ${product.name}`}
                  title="Remove low-stock flag"
                >
                  <X className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
