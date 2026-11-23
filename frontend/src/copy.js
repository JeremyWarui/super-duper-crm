// The website's and the console's shared words. No screen hard-codes them.
const COPY = {
  tagline: "Official campaign website",
  join: { label: "Volunteer", to: "/volunteer" },
  nav: [
    { label: "About", to: "/about" },
    { label: "Agenda", to: "/agenda" },
    { label: "News", to: "/news" },
    { label: "Events", to: "/events" },
    { label: "Media", to: "/media" },
    { label: "Volunteer", to: "/volunteer" },
  ],
  footer: [
    { title: "Take part", links: [["Volunteer", "/volunteer"], ["Events", "/events"], ["Contribute", "/contribute"]] },
    { title: "The campaign", links: [["About", "/about"], ["Agenda", "/agenda"]] },
    { title: "Media", links: [["News & statements", "/news"], ["Videos & documents", "/media"]] },
    { title: "Accounts", links: [["Team sign in", "/signin"]] },
  ],
  newsTitle: "Get campaign news by SMS or email",
  newsLead: "Statements and events near you. Unsubscribe any time.",
  unsubscribe: "Stop campaign news by SMS or email for the contact this link came with.",
  contributeLead: "Your contribution funds the campaign's work on the ground. Contributions are declared as the law requires.",
  owner: "the campaign",
  signInLead: "The campaign team and mobilizers sign in here. One account, routed to the right place.",
  signInAccount: "Use the email and password of your campaign account.",
  signInJoinAsk: "Want to help?",
  consoleRoot: "Campaign admin",
  superAdmin: "Super admin",
  settingsTab: "Site settings",
  help: "The campaign office can reset a password, change your access, or explain a page.",
  helpNoContacts: "The campaign office has not added its contacts yet.",
  supportersSub: "Private to your campaign team.",
  volunteersNone: "None yet. Volunteers sign up on the campaign website.",
  linkPlaceholder: "https:// or /volunteer",
  agendaHome: "/agenda",
  issueCta: { title: "Help win on this issue", label: "Volunteer", to: "/volunteer" },
};

/** The words for this installation. */
export function useCopy() {
  return COPY;
}
