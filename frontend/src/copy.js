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
};

const ASPIRANT = {
  tagline: "Official campaign website",
  join: { label: "Volunteer", to: "/volunteer" },
  nav: [
    { label: "News", to: "/news" },
    { label: "Events", to: "/events" },
    { label: "Volunteer", to: "/volunteer" },
  ],
  footer: [
    { title: "Take part", links: [["Volunteer", "/volunteer"], ["Events", "/events"], ["Contribute", "/contribute"]] },
    { title: "Media", links: [["News & statements", "/news"]] },
    { title: "Accounts", links: [["Team sign in", "/signin"]] },
  ],
  newsTitle: "Get campaign news by SMS or email",
  newsLead: "Statements and events near you. Unsubscribe any time.",
  unsubscribe: "Stop campaign news by SMS or email for the contact this link came with.",
  contributeLead: "Your contribution funds the campaign's work on the ground. Contributions are declared as the law requires.",
  noInstructions: "The campaign has not added how to give yet.",
  organisation: "the campaign",
};

/** The words for this installation; a party's until the site settings say otherwise. */
export function useCopy() {
  return useInstall().aspirant ? ASPIRANT : PARTY;
}
