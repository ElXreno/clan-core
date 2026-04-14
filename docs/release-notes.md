# clan-core release notes 25.11

<!-- This is not rendered yet -->

## New features

### Post-Quantum Hybrid Age Keys (Opt-In)

Clan-cli can now generate post-quantum hybrid age keys (ML-KEM-768 + X25519 via
HPKE) for both admin and machine identities, opt-in via a new flake option:

```nix
clan.vars.settings.age.postQuantum = true;
```

When enabled, `clan vars keygen`, `clan secrets key generate`, and the
automatic machine key generation in the sops and age secret backends all call
`age-keygen -pq` instead of the classical X25519 generator. The resulting
recipients use the `age1pq1...` Bech32 prefix and identities use
`AGE-SECRET-KEY-PQ-1...`.

sops-nix decrypts both classical and hybrid identities transparently.
Encrypted data is protected against future cryptographically-relevant quantum
computers under the store-now-decrypt-later threat model.

To bootstrap a new PQ-only clan in one step, pass `--post-quantum` to
`clan init`. This writes `vars.settings.age.postQuantum = true;` into the
generated `clan.nix` and generates the initial admin key as a hybrid
identity. The same `--post-quantum` flag is also available on
`clan secrets key generate` and `clan vars keygen` for generating a PQ key
without flipping the flake option.

#### Caveats

- **sops backend (default)**: per-recipient independent wraps, so mixing
  classical and post-quantum recipients on the same file works. Rotation can
  be incremental, one machine at a time.
- **age backend** (`secretStore = "age"`): age refuses to mix post-quantum
  and classical recipients in a single `.age` file because the classical
  recipient would silently downgrade the PQ user's security. If you use this
  backend, rotate every recipient of each secret atomically.
- **Recipient size**: hybrid recipients are roughly 2 KB vs 62 bytes for
  X25519. Every committed `sops/*/secret` file grows by ~2 KB per recipient,
  and git diffs are noisier.
- **No forward secrecy**: like classical age, the hybrid construction is a
  one-shot KEM, not a ratcheted protocol.

#### Migrating an existing clan (sops backend)

1. Generate a post-quantum admin identity alongside your classical one:

    ```text
   age-keygen -pq >> ~/.config/sops/age/keys.txt
    ```

2. Register the new public key on your admin user. This re-encrypts every
   file the user is a recipient of and commits the result:

    ```text
   clan secrets users add-key <user> --age-key <pq-pubkey>
    ```

3. Rotate each machine one at a time. `clan vars fix` regenerates the
   machine key as a post-quantum hybrid (thanks to the flake option),
   re-encrypts that machine's vars, and commits. `clan machines update`
   uploads the new bootstrap age.key to the host before activation:

    ```text
   rm -rf sops/machines/<M> sops/secrets/<M>-age.key
   clan vars fix <M>
   clan machines update <M>
    ```

4. Once every admin and machine is on post-quantum, optionally remove the
   classical admin recipient with `clan secrets users remove-key` to drop
   the classical wrap from every file.

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
