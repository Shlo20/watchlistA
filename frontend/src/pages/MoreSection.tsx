import { Users, Settings, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface Props {
  onNavigate: (section: "contacts" | "settings") => void;
}

const ITEMS = [
  { id: "contacts" as const, label: "People", description: "Manage contacts", icon: Users },
  { id: "settings" as const, label: "Settings", description: "Profile & preferences", icon: Settings },
];

export default function MoreSection({ onNavigate }: Props) {
  return (
    <div className="px-4 py-6 mx-auto w-full max-w-[32rem] space-y-4">
      <h2 className="text-xl font-semibold">More</h2>
      <Card>
        <CardContent className="pt-4 pb-2">
          <ul className="divide-y">
            {ITEMS.map(({ id, label, description, icon: Icon }) => (
              <li key={id}>
                <button
                  type="button"
                  onClick={() => onNavigate(id)}
                  className="w-full flex items-center gap-4 py-3.5 min-h-[56px] hover:bg-muted/50 -mx-2 px-2 rounded-md transition-colors"
                >
                  <div className="flex items-center justify-center size-9 rounded-xl bg-muted shrink-0">
                    <Icon className="size-4 text-foreground" />
                  </div>
                  <div className="flex-1 text-left">
                    <p className="text-sm font-medium">{label}</p>
                    <p className="text-xs text-muted-foreground">{description}</p>
                  </div>
                  <ChevronRight className="size-4 text-muted-foreground shrink-0" />
                </button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
