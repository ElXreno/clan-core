import type { Plugin } from "unified";
import type { Root } from "mdast";
import * as config from "../../clan-site.config.ts";
import { visit } from "unist-util-visit";

/**
 * Add version to /docs/ links
 */
const remarkDocsLinks: Plugin<[], Root> = function () {
  return (tree) => {
    visit(tree, ["link", "definition"] as const, (node) => {
      if (!node.url.startsWith(`${config.docsBase}/`)) {
        return;
      }

      const path = node.url.slice(config.docsBase.length + 1);
      node.url = `${config.docsBase}/${config.version}${path ? `/${path}` : ""}`;
    });
  };
};
export default remarkDocsLinks;
