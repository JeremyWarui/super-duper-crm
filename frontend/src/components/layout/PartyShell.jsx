import { AppLayout } from "@/components/layout/AppLayout";
import { AppPage } from "@/components/layout/AppPage";
import { ConsoleTools } from "@/components/layout/ConsoleTools";
import { useInstall } from "@/app/site";
import { useCopy } from "@/copy";
import { displayName } from "@/lib/format";
import { homeOf } from "@/lib/home";
import { officeOf } from "@/lib/labels";
import { partyNav } from "@/lib/partyNav";
import { useAuth } from "@/store/auth";

/** The party CRM's frame around one page; a page without a `kit` title renders its own header. */
export function PartyShell({ crumb, page, children }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const { aspirant } = useInstall();
  const copy = useCopy();
  const office = officeOf(user, copy.superAdmin);
  return (
    <AppLayout
      tone="dark"
      nav={partyNav(user, { aspirant })}
      rootLabel={copy.consoleRoot}
      rootPath={homeOf(user)}
      subtitle={office}
      user={{ name: displayName(user), role: office }}
      onSignOut={logout}
      tools={<ConsoleTools />}
      slotHeaders
    >
      <AppPage crumb={crumb} context={page?.context} title={page?.title}>{children}</AppPage>
    </AppLayout>
  );
}
