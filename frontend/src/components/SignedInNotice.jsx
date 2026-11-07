import { useAuth } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/** A full-page notice for a login with nowhere to go: "You are signed in as …" followed by `rest`, and Sign out. */
export default function SignedInNotice({ title, rest }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  return (
    <div className="flex min-h-dvh items-center justify-center bg-background p-4">
      <Card variant="outline" className="w-full max-w-[420px] gap-2">
        <h1 className="font-display text-card-title font-bold">{title}</h1>
        <p className="leading-[1.6] text-muted-foreground">You are signed in as {user?.username}{rest}</p>
        <Button variant="quiet" shape="rounded" className="mt-3 self-start" onClick={logout}>
          Sign out
        </Button>
      </Card>
    </div>
  );
}

/** For a login that is on no campaign: only the superuser puts logins on campaigns. */
export const NoCampaign = () => (
  <SignedInNotice
    title="You are not on a campaign yet"
    rest=", but this login is not on any campaign. Ask whoever runs your campaign, or contact support."
  />
);
