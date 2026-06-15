import { useState } from "react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { updateMe } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export default function SettingsSection() {
  const { user, updateUser } = useAuth();
  const [name, setName] = useState(user?.name ?? "");
  const [businessName, setBusinessName] = useState(user?.business_name ?? "");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await updateMe({
        name: name.trim() || undefined,
        business_name: businessName.trim() || null,
      });
      updateUser(updated);
      toast.success("Settings saved");
    } catch {
      toast.error("Couldn't save settings. Try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-4">
      <h2 className="text-xl font-semibold">Settings</h2>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="settings-name">Display name</Label>
            <Input
              id="settings-name"
              className="h-11"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="settings-biz">Business name</Label>
            <Input
              id="settings-biz"
              className="h-11"
              placeholder="Optional — shown on quotes and lists"
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
            />
          </div>
          <Button
            className="w-full h-11"
            disabled={saving || !name.trim()}
            onClick={handleSave}
          >
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
