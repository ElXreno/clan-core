# clan-core release notes 25.11

<!-- This is not rendered yet -->

## New features

### Post-Quantum Hybrid Age Keys by Default

`clan-cli` now generates post-quantum hybrid age keys (ML-KEM-768 + X25519)
via `age-keygen -pq`. New admin and machine identities use the `age1pq1...`
Bech32 prefix.

`sops-nix` decrypts classical and hybrid identities transparently, so
existing classical keys keep working. When `clan` commands that touch
secrets (`vars generate|fix|check|upload`, `secrets key generate`,
`secrets users add-key`, `machines update|install`) detect classical
recipients in the flake, they print a one-time warning pointing to the
migration guide.

The age backend (`secretStore = "age"`) refuses to mix PQ and classical
recipients in a single file; rotate all recipients atomically if you use
that backend.

See [Migrate to Post-Quantum Hybrid Age Keys](/docs/guides/migrations/migrate-to-post-quantum-age)
for the step-by-step migration procedure.

### New Monitoring Service

Clan now provides a monitoring service based on the grafana stack.
The service consists of a server and a client role.
Servers store metrics and logs.
They also provide optional dashboards for visualization and an alerting system.
Clients are machines that create metrics and logs.
Those are sent to the central monitoring server for storage and visualization.

## ncps

- Added the ncps nix proxy binary cache service.

- Standardized exports system with centrally-defined options in clan-core

**Darwin Support**

- Services now support nix-darwin alongside NixOS
- Service authors can provide `darwinModule` in addition to `nixosModule` in their service definitions
- WireGuard service now fully supports darwin machines using wg-quick interfaces
- Added `clan.core.networking.extraHosts` for managing /etc/hosts on darwin via launchd

**SSH Agent Forwarding**

- Added configurable SSH agent forwarding for deployments
    - Disabled by default for security
    - Configure per-machine: `inventory.machines.<name>.deploy.forwardAgent = true;`
    - Configure globally: `clan.core.networking.forwardAgent = true;`
    - See [SSH Agent Forwarding Guide](https://docs.clan.lol/guides/ssh-agent-forwarding)

## Breaking Changes

### Monitoring Service

The old monitoring service including telegraf has been marked deprecated for a while.
The following things related to the old monitoring stack have been removed:

- the telegraf role in `inventory.instances.monitoring.roles.telegraf`
- options related to the telegraf role:
    - `inventory.instances.monitoring.roles.telegraf.tags.all.settings.allowAllInterfaces`
    - `inventory.instances.monitoring.roles.telegraf.tags.all.settings.interfaces`

### Internet Service

The `settings.host` option in the internet service now only accepts a hostname or IP address. Port and user must be specified separately using the new `settings.port` and `settings.user` options.

**Migration:**

- **Before:** `settings.host = "root@example.com:2222";`
- **After:**

    ```nix
  settings.host = "example.com";
  settings.port = 2222;
  settings.user = "root";
    ```

The `settings.port` defaults to `22` and `settings.user` defaults to `null` (which uses `root`).

### Exports

- **Experimental** exports system has been redesigned.
    - Previous export definitions are no longer compatible
    - **Migration required**: Update your modules to use the standardized export options

### Clan Password Store Backend

The `clan.core.vars.password-store.passPackage` option has been removed. The
default backend for clan password store is now `passage` (age-based encryption).

**Migration:**

- **Before:** `clan.core.vars.password-store.passPackage = pkgs.passage;`
- **After:** `clan.core.vars.password-store.passCommand = "passage";`
j
The new `passCommand` option specifies the command name to execute for password
store operations. The command must be available in the system PATH and needs to
be installed by the user (e.g., via `environment.systemPackages`).

The backend now defaults to passage/age, providing improved security through age
encryption. If you were explicitly setting `passPackage`, you should update your
configuration to use `passComma

**SSH Agent Forwarding**

- Disabled by default (was previously enabled)
    - If your deployments rely on SSH agent forwarding to access private Git repositories, you must now explicitly enable it
    - See migration guide in [SSH Agent Forwarding documentation](https://docs.clan.lol/guides/ssh-agent-forwarding)

## Misc

### Facts got removed

The `facts` system has been fully removed from clan-core. The automatic migration feature (`migrateFact`) is no longer available.
Since the deprecation of facts happened already a while ago, all your facts should be migrated to vars automatically by now.
If not, have a look at the [migration guide](https://docs.clan.lol/guides/migrations/migration-facts-vars/)
