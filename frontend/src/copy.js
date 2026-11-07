// The words that differ between a party's website and an aspirant's. No screen hard-codes them.
import { useInstall } from "./app/site";

const PARTY = {
  tagline: "Registered political party",
  join: { label: "Join the party", to: "/join-party" },
  nav: [
    { label: "About", to: "/about" },
    { label: "News", to: "/news" },
    { label: "Events", to: "/events" },
    { label: "Candidates", to: "/candidates" },
    { label: "Results", to: "/results" },
    { label: "Counties", to: "/counties" },
  ],
  footer: [
    { title: "The party", links: [["About", "/about"], ["Leadership", "/leadership"], ["Manifesto", "/manifesto"]] },
    { title: "Take part", links: [["Join the party", "/join-party"], ["Events", "/events"], ["Contribute", "/contribute"], ["Vie with us", "/vie"], ["Our candidates", "/candidates"]] },
    { title: "Media", links: [["News & statements", "/news"], ["Primary results", "/results"]] },
    { title: "Accounts", links: [["Member sign in", "/signin"]] },
  ],
  newsTitle: "Get party news by SMS or email",
  newsLead: "Statements, events near you and nomination notices. Unsubscribe any time.",
  unsubscribe: "Stop party news by SMS or email for the contact this link came with.",
  contributeLead: "Your contribution funds the party's work in every county. Contributions are declared as the law requires.",
  noInstructions: "The party has not added how to give yet.",
  organisation: "the party",
  signInLead: "Members, candidate teams, mobilizers and party staff sign in here. One account, routed to the right place.",
  signInAccount: "Use the email and password of your party account.",
  signInJoinAsk: "Not a member yet?",
  consoleRoot: "Party CRM",
  superAdmin: "Party super admin",
  settingsTab: "Party",
  help: "The party office can reset a password, change your office, or explain a page.",
  helpNoContacts: "The party office has not added its contacts yet.",
  supportersSub: "Private to your campaign team. Never shared with the party.",
  volunteersNone: "None yet. Volunteers sign up on the candidate's page on the party website.",
  linkPlaceholder: "https:// or /join-party",
  newsKicker: "From the party",
  agendaMore: { label: "Read the manifesto", to: "/manifesto" },
  agendaHome: "/#issues",
  issueCta: { title: "Help shape the party's agenda", label: "Join to shape our agenda", to: "/join-party" },
};

const ASPIRANT = {
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
  noInstructions: "The campaign has not added how to give yet.",
  organisation: "the campaign",
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
  newsKicker: "From the campaign",
  agendaMore: { label: "See the whole agenda", to: "/agenda" },
  agendaHome: "/agenda",
  issueCta: { title: "Help win on this issue", label: "Volunteer", to: "/volunteer" },
};

/** The words for this installation; a party's until the site settings say otherwise. */
export function useCopy() {
  return useInstall().aspirant ? ASPIRANT : PARTY;
}
