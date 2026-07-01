import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { requestCode, registerApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

// Map a FastAPI validation-error field to a message a person can act on.
const FIELD_MESSAGES: Record<string, string> = {
  password: "Password must be at least 8 characters.",
  name: "Please enter your name.",
  phone: "That phone number doesn't look valid.",
  code: "Please enter the 6-digit code you received.",
};

export default function RegisterPage() {
  const navigate = useNavigate();
  const { completeAuth } = useAuth();

  const [step, setStep] = useState<"phone" | "details">("phone");
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleRequestCode(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setLoading(true);
    try {
      await requestCode(phone);
      toast.success("Code sent — check your phone");
      setStep("details");
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 422) {
        toast.error("That phone number doesn't look valid — check it and try again.");
      } else {
        toast.error("Couldn't send code. Check your connection and try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;

    if (password.length < 8) {
      toast.error("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      const response = await registerApi({ name, phone, password, code });
      completeAuth(response);
      toast.success("Account created — welcome!");
      navigate("/");
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: unknown } };
      const httpStatus = axiosErr?.response?.status;
      const body = axiosErr?.response?.data as { detail?: unknown } | undefined;

      if (httpStatus === 422) {
        // FastAPI validation error — name the offending field so the message
        // matches the real cause instead of always blaming the password.
        let msg = "Please check your details and try again.";
        const detail = body?.detail;
        if (Array.isArray(detail) && detail.length > 0) {
          const first = detail[0] as { msg?: string; loc?: Array<string | number> };
          const field = first.loc?.[first.loc.length - 1];
          if (typeof field === "string" && FIELD_MESSAGES[field]) {
            msg = FIELD_MESSAGES[field];
          } else if (first.msg) {
            msg = first.msg;
          }
        } else if (typeof detail === "string") {
          msg = detail;
        }
        toast.error(msg);
      } else if (httpStatus === 401) {
        toast.error("Invalid or expired verification code.");
      } else if (httpStatus === 409) {
        toast.error("This phone number is already registered — try logging in.");
      } else {
        toast.error("Couldn't create account, please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 py-8">
      <Card className="w-full max-w-sm">
        <CardHeader className="pb-2 pt-6 px-6">
          <h1 className="text-3xl font-bold tracking-tight">
            Watch<span className="text-primary">list</span>
          </h1>
          <p className="text-sm text-muted-foreground mt-1">Create an account</p>
        </CardHeader>
        <CardContent className="px-6 pb-6">
          {step === "phone" ? (
            <form onSubmit={handleRequestCode} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="phone">Phone number</Label>
                <Input
                  id="phone"
                  type="tel"
                  placeholder="5555550100"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  required
                  autoComplete="tel"
                  className="h-11"
                />
              </div>
              <Button type="submit" size="lg" className="w-full mt-2" disabled={loading}>
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Send code
              </Button>
              <p className="text-center text-xs text-muted-foreground">
                Already have an account?{" "}
                <Link to="/login" className="text-primary hover:underline">
                  Sign in
                </Link>
              </p>
            </form>
          ) : (
            <form onSubmit={handleRegister} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="name">Full name</Label>
                <Input
                  id="name"
                  type="text"
                  placeholder="Jane Smith"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  autoComplete="name"
                  className="h-11"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  className="h-11"
                />
                <p className="text-xs text-muted-foreground">At least 8 characters.</p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="code">6-digit code</Label>
                <Input
                  id="code"
                  type="text"
                  inputMode="numeric"
                  pattern="\d{6}"
                  maxLength={6}
                  placeholder="000000"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                  className="h-11"
                />
              </div>
              <Button type="submit" size="lg" className="w-full mt-2" disabled={loading}>
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create account
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="w-full text-xs"
                onClick={() => setStep("phone")}
                disabled={loading}
              >
                ← Change phone number
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
