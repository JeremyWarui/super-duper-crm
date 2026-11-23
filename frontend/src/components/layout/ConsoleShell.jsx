import { AppLayout } from "@/components/layout/AppLayout";
import { AppPage } from "@/components/layout/AppPage";
import { HelpPanel } from "@/components/layout/TopBarTools";
import { useCopy } from "@/copy";
import { displayName } from "@/lib/format";
import { homeOf } from "@/lib/home";
import { useAuth } from "@/store/auth";

/** The superuser console's frame around one page, with the console link and help in the top bar. */
export function ConsoleShell({ crumb, page, children }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const copy = useCopy();
  return (
    <AppLayout
      tone="dark"
      nav={[{ label: "Console", to: "/console" }]}
      rootLabel={copy.consoleRoot}
      rootPath={homeOf(user)}
      subtitle={copy.superAdmin}
      user={{ name: displayName(user), role: copy.superAdmin }}
      onSignOut={logout}
      tools={<HelpPanel id="console-help" lead={copy.help} none={copy.helpNoContacts} />}
      slotHeaders
    >
      <AppPage crumb={crumb} context={page?.context} title={page?.title}>{children}</AppPage>
    </AppLayout>
  );
}
