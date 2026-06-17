import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { requestCode, registerApi } from "@/lib/api";
import { saveAuth } from "@/lib/auth";

export default function RegisterPage() {
  const navigate = useNavigate();

  const [step, setStep] = useState<"phone" | "details">("phone");
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleRequestCode(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await requestCode(phone);
      toast.success("Code sent — check your phone");
      setStep("details");
    } catch {
      toast.error("Couldn't send code. Check the phone number and try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();

    if (password.length < 8) {
      toast.error("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      const response = await registerApi({ name, phone, password, code });
      saveAuth(response.access_token, response.user);
      toast.success("Account created — welcome!");
      navigate("/");
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: unknown } };
      const httpStatus = axiosErr?.response?.status;
      const body = axiosErr?.response?.data as { detail?: unknown } | undefined;

      if (httpStatus === 422) {
        // FastAPI validation error — surface the real message if available
        let msg = "Please check your details — password must be at least 8 characters.";
        const detail = body?.detail;
        if (Array.isArray(detail) && detail.length > 0) {
          const first = detail[0] as { msg?: string };
          if (first.msg) msg = first.msg;
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
