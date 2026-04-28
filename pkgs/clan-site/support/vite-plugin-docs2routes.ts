// This file exists inside the clan-site package instead of as a standalone
// package because it's for clan-site specifically and use clan-site specific
// import specifier like #lib, which won't work in an independent package
import type { PluginOption } from "vite";
import * as config from "#config";
import pathutil from "node:path";
import { ServerDocs } from "#lib/models/docs/docs.server.ts";
import { spawn } from "node:child_process";

const siteConfigPath = pathutil.resolve(
  import.meta.dirname,
  "../clan-site.config.ts",
);
export default function vitePluginDocs2routes(): PluginOption {
  let docs: ServerDocs;
  return {
    name: "vite-plugin-docs2routes",
    config: {
      order: "pre",
      async handler(_config, env): Promise<void> {
        // We guarantee that vite dev is always after vite build
        // So we only do clean up and type generation at vite build
        if (env.command === "build") {
          await run_git_clean();
        }
        docs = await ServerDocs.init();
        if (env.command === "build") {
          await run_sveltekit_sync();
        }
      },
    },
    configureServer(server): void {
      const [dir] = config.docsSrcDirs;
      function isRenderable(filename: string): boolean {
        return (
          (filename.endsWith(".md") || filename.endsWith(".svelte")) &&
          filename.startsWith(`${dir}/`)
        );
      }

      server.watcher.add([siteConfigPath, dir]);
      server.watcher.on("change", (filename) => {
        if (filename === siteConfigPath) {
          (async (): Promise<void> => {
            docs = await ServerDocs.init();
          })();
          return;
        }
        if (!isRenderable(filename)) {
          return;
        }
        (async (): Promise<void> => {
          await docs.renderFile(filename);
        })();
      });
      server.watcher.on("add", (filename) => {
        if (!isRenderable(filename)) {
          return;
        }
        (async (): Promise<void> => {
          await docs.renderFile(filename);
        })();
      });
      server.watcher.on("unlink", (filename) => {
        if (!isRenderable(filename)) {
          return;
        }
        (async (): Promise<void> => {
          await docs.removeFile(filename);
        })();
      });
    },
  };
}

async function run_git_clean(): Promise<number | null> {
  const dir = pathutil.resolve(import.meta.dirname, "../src/routes");
  const args = ["clean", "-dfx", dir];
  const p = spawn("git", args, {
    cwd: pathutil.resolve(import.meta.dirname, ".."),
  });
  const { resolve, reject, promise } = Promise.withResolvers<number | null>();
  p.on("error", (code) => {
    reject(new Error(`git ${args.join(" ")} exited with code ${code}`));
  });
  p.on("close", (code) => {
    resolve(code);
  });
  return await promise;
}

// Generate types with svelte-kit sync
async function run_sveltekit_sync(): Promise<number | null> {
  const cmd = pathutil.resolve(
    import.meta.dirname,
    "../node_modules/.bin/svelte-kit",
  );
  const p = spawn(cmd, ["sync"], {
    cwd: pathutil.resolve(import.meta.dirname, ".."),
  });
  const { resolve, reject, promise } = Promise.withResolvers<number | null>();
  p.on("error", (code) => {
    reject(new Error(`svelte-kit sync exited with code ${code}`));
  });
  p.on("close", (code) => {
    resolve(code);
  });
  return await promise;
}
