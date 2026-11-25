// The browser tab's title: the page's own title, then the site's name.
import { useEffect } from "react";

let page = "";
let site = "";

const apply = () => {
  const title = page && site ? `${page} | ${site}` : page || site;
  if (title) document.title = title;
};

/** Set the site's name, the tab title's second part. */
export function setSiteName(name) {
  site = name || "";
  apply();
}

/** Show `title` before the site's name while the calling page is on screen. */
export function usePageTitle(title) {
  useEffect(() => {
    page = typeof title === "string" ? title : "";
    apply();
    return () => {
      page = "";
      apply();
    };
  }, [title]);
}
