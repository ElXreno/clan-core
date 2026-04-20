# Migrate to Post-Quantum Hybrid Age Keys

Starting with clan-core 25.11, `clan-cli` generates post-quantum hybrid age
keys (ML-KEM-768 + X25519) by default via `age-keygen -pq`. New admin and
machine identities use the `age1pq1...` Bech32 prefix and their private keys
use the `AGE-SECRET-KEY-PQ-1...` prefix.

`sops-nix` decrypts classical (`age1...`) and hybrid (`age1pq1...`) identities
transparently, so existing classical keys keep working and no migration is
strictly required. When `clan` commands that touch secrets
(`vars generate|fix|check|upload`, `secrets key generate`,
`secrets users add-key`, `machines update|install`) detect classical recipients
in the flake, they print a one-time warning pointing to this guide.

:::admonition[Age backend constraint]{type=warning}
The age backend (`secretStore = "age"`) stores each secret in a raw `.age`
file with a single recipient list, and the `age` binary refuses mixed
post-quantum and classical recipients (`age: error: incompatible recipients`).
The age-backend migration is therefore a coordinated rotation — see the
[Age backend](#age-backend) section below. The sops backend wraps each
recipient independently and tolerates mixed recipient sets during the
migration window.
:::

## Sops backend (default)

### 1. Generate a post-quantum admin identity

Append a new hybrid key to your existing age keys file:

```shellSession
age-keygen -pq >> ~/.config/sops/age/keys.txt
```

The command prints the new public key to stderr. Note it down for the next
step — it starts with `age1pq1`.

:::admonition[Why not `clan secrets key generate`?]{type=note}
`clan secrets key generate` **overwrites** `~/.config/sops/age/keys.txt` with
only the new key. During migration you need both identities present
simultaneously so you can still decrypt classical-wrapped secrets while
re-encrypting them to post-quantum recipients.
:::

### 2. Register the new public key on your admin user

```shellSession
clan secrets users add-key <user> --age-key <pq-pubkey>
```

This adds the hybrid recipient alongside your classical one. Existing secrets
are re-wrapped so the new key can decrypt them.

### 3. Rotate each machine's key

`clan vars fix` regenerates the machine age key when it is missing. Delete the
existing sops artifacts and run it:

```shellSession
rm -rf sops/machines/<M> sops/secrets/<M>-age.key
clan vars fix <M>
clan machines update <M>
```

`clan machines update` deploys the new machine key before activation so the
target still decrypts its secrets across the rotation.

Repeat for every machine in the clan.

### 4. Remove the classical admin recipient

Once every user and machine has a post-quantum recipient, drop the classical
admin key so new secrets are only wrapped to hybrid recipients:

```shellSession
clan secrets users remove-key <user> --age-key <classical-pubkey>
```

After this, the classical line can be deleted from
`~/.config/sops/age/keys.txt` as well.

### 5. Verify the migration

The warning emitted by `clan` commands disappears once the flake contains no
classical age recipients. To check manually, recipients live under
`sops/users/*/key.json` and `sops/machines/*/key.json`; each `publickey`
should start with `age1pq1`.

## Age backend

This section applies when your machines use
`clan.core.vars.settings.secretStore = "age"`.

The age backend stores machine keys under `secrets/age-keys/machines/<M>/`
and encrypted values under `secrets/clan-vars/`, each as a raw `.age` file
with a sidecar `*.age.recipients`. Because raw `age` refuses mixed
post-quantum and classical recipients, the migration happens in two passes:
steps 1-3 rotate the admin identity (non-destructive), steps 4-9 rotate
machine keypairs using capture-and-replay to preserve every secret value,
and steps 10-11 handle cleanup and verification.

Unlike the sops backend, user recipients for the age backend are declared in
flake-level Nix config, not via `clan secrets users`:

```nix
clan.vars.settings.recipients.hosts.<machine> = [ "<admin-pubkey>" ];
# or, as a fallback applied to any machine without a per-host entry:
clan.vars.settings.recipients.default = [ "<admin-pubkey>" ];
```

### 1. Generate a post-quantum admin identity

Append a new hybrid key to your existing age keys file:

```shellSession
age-keygen -pq >> ~/.config/sops/age/keys.txt
```

Keep the classical line in place for now — you'll still need it to decrypt
existing artifacts until step 9.

### 2. Replace the classical admin pubkey in the flake

Edit every `clan.vars.settings.recipients.hosts.*` and
`clan.vars.settings.recipients.default` entry to use the new `age1pq1...`
pubkey instead of the classical one. Commit the change.

### 3. Re-encrypt to the new admin recipient

```shellSession
clan vars fix
```

`clan vars fix` decrypts each machine's `key.age` using the classical admin
identity (still present in `keys.txt`) and rewraps it to the new post-quantum
admin recipient. Machine pubkeys and the per-machine or shared `.age` files
stay untouched — they keep their existing machine-side encryption and remain
decryptable on target without any change.

### 4. Capture every deploy=true secret to plaintext

Collect every per-machine and shared secret value to a temporary directory
that is **not** inside your clan flake. For example:

```shellSession
mkdir -m 700 -p /tmp/pq-replay

# Per-machine deploy=true
for m in m1 m2; do
  mkdir -p /tmp/pq-replay/$m
  clan vars get $m svc/token > /tmp/pq-replay/$m/svc_token
done

# Shared (one copy is enough — re-applied against any machine)
mkdir -p /tmp/pq-replay/shared
clan vars get m1 shared/db_password > /tmp/pq-replay/shared/db_password
```

Admin can reach the plaintext through `key.age`: admin PQ identity decrypts
`key.age` → machine private key → per-machine or shared `.age` file.

### 5. Purge old machine keypairs and encrypted values

```shellSession
rm -rf secrets/age-keys/machines secrets/clan-vars
```

This removes the old machine keypairs and every `.age` file encrypted to
them.

### 6. Regenerate machine keypairs with the new recipient

```shellSession
clan vars generate
```

This creates a fresh `age1pq1...` keypair for every machine and runs each
generator once to produce placeholder values.

### 7. Replay captured plaintexts

```shellSession
for m in m1 m2; do
  clan vars set $m svc/token < /tmp/pq-replay/$m/svc_token
done
clan vars set m1 shared/db_password < /tmp/pq-replay/shared/db_password
```

`clan vars set` re-encrypts each value against the current machine pubkeys,
which are now all post-quantum, so the resulting `.age` files have a
homogeneous post-quantum recipient set.

### 8. Shred the capture directory

```shellSession
rm -rf /tmp/pq-replay
```

### 9. Deploy every machine

```shellSession
clan machines update <M>
```

Repeat for every machine in the clan. `clan machines update` uploads the new
machine private key before activation so the target can decrypt its secrets
on the next boot.

### 10. Remove the classical admin key

Once every machine is running with the new post-quantum key, delete the
classical line from `~/.config/sops/age/keys.txt`.

### 11. Verify the migration

The warning emitted by `clan` commands disappears once every scanned
recipient is post-quantum. To check manually, machine pubkeys live under
`secrets/age-keys/machines/*/pub` and recipient lists under
`*.age.recipients`; each entry should start with `age1pq1`.
