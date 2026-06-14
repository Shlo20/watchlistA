import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Pencil, Trash2, Plus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  listContacts,
  createContact,
  updateContact,
  deleteContact,
  type Contact,
} from "@/lib/api";

function apiErr(err: unknown): number | undefined {
  return (err as { response?: { status?: number } })?.response?.status;
}

export default function ContactsSection() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);

  const [showAdd, setShowAdd] = useState(false);
  const [addNickname, setAddNickname] = useState("");
  const [addPhone, setAddPhone] = useState("");
  const [adding, setAdding] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNickname, setEditNickname] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listContacts()
      .then(setContacts)
      .catch(() => toast.error("Couldn't load contacts."))
      .finally(() => setLoading(false));
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setAdding(true);
    try {
      const c = await createContact({
        nickname: addNickname.trim(),
        phone: addPhone.trim(),
      });
      setContacts((prev) => [c, ...prev]);
      setAddNickname("");
      setAddPhone("");
      setShowAdd(false);
      toast.success("Contact added");
    } catch (err) {
      const status = apiErr(err);
      if (status === 409) toast.error("That phone is already in your contacts.");
      else if (status === 422) toast.error("Invalid phone number format.");
      else toast.error("Couldn't add contact. Try again.");
    } finally {
      setAdding(false);
    }
  }

  function startEdit(c: Contact) {
    setEditingId(c.id);
    setEditNickname(c.nickname);
    setEditPhone(c.phone);
  }

  async function handleSaveEdit(id: number) {
    setSaving(true);
    try {
      const updated = await updateContact(id, {
        nickname: editNickname.trim(),
        phone: editPhone.trim(),
      });
      setContacts((prev) => prev.map((c) => (c.id === id ? updated : c)));
      setEditingId(null);
      toast.success("Contact updated");
    } catch (err) {
      const status = apiErr(err);
      if (status === 409) toast.error("That phone is already in use.");
      else if (status === 422) toast.error("Invalid phone number format.");
      else toast.error("Couldn't save. Try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteContact(id);
      setContacts((prev) => prev.filter((c) => c.id !== id));
      if (editingId === id) setEditingId(null);
      toast.success("Contact removed");
    } catch {
      toast.error("Couldn't delete. Try again.");
    }
  }

  return (
    <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Contacts</h2>
        <Button size="sm" onClick={() => setShowAdd((s) => !s)}>
          <Plus className="size-4 mr-1" />
          Add
        </Button>
      </div>

      {showAdd && (
        <Card>
          <CardContent className="pt-4">
            <form onSubmit={handleAdd} className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="add-nickname">Nickname</Label>
                <Input
                  id="add-nickname"
                  placeholder="Ali's Store"
                  value={addNickname}
                  onChange={(e) => setAddNickname(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="add-phone">Phone</Label>
                <Input
                  id="add-phone"
                  type="tel"
                  placeholder="5555550100"
                  value={addPhone}
                  onChange={(e) => setAddPhone(e.target.value)}
                  required
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={adding} className="flex-1">
                  {adding ? "Adding…" : "Add contact"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowAdd(false)}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="pt-4">
          {loading ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              Loading…
            </p>
          ) : contacts.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              No contacts yet. Add one above.
            </p>
          ) : (
            <ul className="divide-y">
              {contacts.map((c) =>
                editingId === c.id ? (
                  <li key={c.id} className="py-3 space-y-2">
                    <Input
                      value={editNickname}
                      onChange={(e) => setEditNickname(e.target.value)}
                      placeholder="Nickname"
                    />
                    <Input
                      type="tel"
                      value={editPhone}
                      onChange={(e) => setEditPhone(e.target.value)}
                      placeholder="Phone"
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleSaveEdit(c.id)}
                        disabled={saving}
                      >
                        {saving ? "Saving…" : "Save"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setEditingId(null)}
                        disabled={saving}
                      >
                        Cancel
                      </Button>
                    </div>
                  </li>
                ) : (
                  <li
                    key={c.id}
                    className="flex items-center gap-3 py-3 min-h-[52px]"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{c.nickname}</p>
                      <p className="text-xs text-muted-foreground">{c.phone}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => startEdit(c)}
                      className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                      aria-label={`Edit ${c.nickname}`}
                    >
                      <Pencil className="size-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(c.id)}
                      className="shrink-0 text-muted-foreground hover:text-destructive transition-colors"
                      aria-label={`Delete ${c.nickname}`}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </li>
                )
              )}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
