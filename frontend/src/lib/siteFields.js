// The website settings the console and the workspace edit, as ConfigFields entries:
// [key, label, max length, { rows }]. Limits match backend/src/backend/schemas/site.py and party.py.

export const SITE_LINES = [
  ["name", "Name", 150],
  ["short_name", "Short name (3 letters or fewer go on the logo tile)", 30],
  ["slogan", "Slogan", 150],
  ["registration_number", "Registration number", 40],
  ["about_headline", "About page headline", 150],
  ["founded_year", "Year founded", 4],
  ["logo_url", "Logo address (https://)", 500],
  ["contact_email", "Contact email", 254],
  ["contact_phone", "Contact phone", 20],
  ["address", "Address", 300],
  ["manifesto_url", "Manifesto address (https://)", 500],
  ["privacy_notice_version", "Privacy notice version", 20],
  ["mpesa_paybill", "M-Pesa Paybill number (leave blank for a Till)", 7],
  ["mpesa_account", "Paybill account number", 20],
  ["mpesa_till", "M-Pesa Till number (leave blank for a Paybill)", 7],
];

export const SITE_TEXTS = [
  ["description", "About (shown on the About page)", undefined, { rows: 6 }],
  ["manifesto_text", "Manifesto text", undefined, { rows: 6 }],
  ["aspirant_steps", "Steps to become an aspirant (one per line)", 20000, { rows: 6 }],
  ["payment_instructions", "How to give (shown on the Contribute page)", 2000, { rows: 4 }],
  ["privacy_notice", "Privacy notice", 20000, { rows: 8 }],
];

/** The entries of `fields` whose key is in `keys`, in the list's order. */
export const only = (fields, keys) => fields.filter(([key]) => keys.includes(key));
