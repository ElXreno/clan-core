{ ... }:
{
  perSystem =
    { ... }:
    {
      clan.nixosTests.nixos-test-age-backend-pq = {

        name = "nixos-test-age-backend-pq";

        clan = {
          # Point the clan directory at the self-contained PQ fixture tree so
          # age.nix discovers encrypted files under ./age-pq/secrets/clan-vars/
          # instead of the classical ./secrets/clan-vars/ used by the sibling test.
          directory = ./age-pq;
          test.useContainers = false;

          machines.machine =
            { lib, pkgs, ... }:
            let
              # Pre-generated fixture: post-quantum hybrid machine private key
              # (ML-KEM-768 + X25519). Encrypted .age files in
              # ./age-pq/secrets/clan-vars/ are wrapped to the matching
              # age1pq1... recipient.
              fixtures = ./age-pq/fixtures;
            in
            {
              clan.core.vars.settings.secretStore = "age";
              clan.core.vars.enableConsistencyCheck = false;
              clan.core.vars.age.secretLocation = lib.mkForce "/etc/secret-vars";
              clan.core.settings.directory = lib.mkForce ./age-pq;

              # ── Generator declarations ──────────────────────────
              # These tell age.nix what activation scripts to create
              # and where decrypted secrets should appear. The generator
              # scripts won't actually run (fixtures are pre-encrypted)
              # but the declarations drive the NixOS-side decryption path.
              clan.core.vars.generators.test-generator = {
                files.service-secret = {
                  secret = true;
                  neededFor = "services";
                };
                files.user-secret = {
                  secret = true;
                  neededFor = "users";
                };
                files.activation-secret = {
                  secret = true;
                  neededFor = "activation";
                };
                script = ''
                  echo -n placeholder > "$out"/service-secret
                  echo -n placeholder > "$out"/user-secret
                  echo -n placeholder > "$out"/activation-secret
                '';
              };
              clan.core.vars.generators.shared-generator = {
                share = true;
                files.shared-secret = {
                  secret = true;
                  neededFor = "services";
                };
                script = ''
                  echo -n placeholder > "$out"/shared-secret
                '';
              };
              clan.core.vars.generators.perm-generator = {
                files.perm-secret = {
                  secret = true;
                  neededFor = "services";
                  owner = "nobody";
                  group = "nogroup";
                  mode = "0440";
                };
                script = ''
                  echo -n placeholder > "$out"/perm-secret
                '';
              };

              # Point the NixOS module at the PQ fixture directory.
              # age.nix auto-discovers .age files under
              # secrets/clan-vars/per-machine/<machine>/ and secrets/clan-vars/shared/.
              # We override that via a symlink during activation so the module
              # finds the PQ fixtures instead of the classical ones.
              #
              # In production the flake directory already contains the right
              # mix of PQ or classical encrypted files; this test uses the
              # symlink trick to reuse the classical test's evaluation path
              # while pointing at a different fixture tree.

              system.activationScripts.mockAgePqUpload = {
                text = ''
                  mkdir -p /etc/secret-vars
                  cp ${fixtures}/key.txt /etc/secret-vars/key.txt
                  chmod 600 /etc/secret-vars/key.txt

                  # Sanity check: the fixture must be a post-quantum hybrid key.
                  # Fail early if a reviewer accidentally substituted a classical key.
                  if ! grep -q '^AGE-SECRET-KEY-PQ-1' /etc/secret-vars/key.txt; then
                    echo "age-pq fixture is not a post-quantum key; aborting" >&2
                    exit 1
                  fi

                  # Simulate activation secrets uploaded as plaintext by the deployer.
                  mkdir -p /etc/secret-vars/activation/test-generator
                  ${pkgs.age}/bin/age --decrypt -i /etc/secret-vars/key.txt \
                    -o /etc/secret-vars/activation/test-generator/activation-secret \
                    ${
                      ./age-pq/secrets/clan-vars/per-machine/machine/test-generator/activation-secret/activation-secret.age
                    }
                  chmod 400 /etc/secret-vars/activation/test-generator/activation-secret
                '';
                deps = [ "specialfs" ];
              };

              # Ensure age.nix activation scripts run after our mock upload
              system.activationScripts.setupSecrets.deps = [ "mockAgePqUpload" ];
              system.activationScripts.setupUserSecrets.deps = [ "mockAgePqUpload" ];
            };
        };

        testScript = ''
          start_all()
          machine.wait_for_unit("multi-user.target")

          # ── Test 1: Activation scripts ran and created ramfs mounts ──
          machine.succeed("mountpoint -q /run/secrets")
          machine.succeed("mountpoint -q /run/user-secrets")

          mount_type = machine.succeed("findmnt -n -o FSTYPE /run/secrets").strip()
          assert mount_type == "ramfs", f"Expected ramfs, got '{mount_type}'"

          mount_type = machine.succeed("findmnt -n -o FSTYPE /run/user-secrets").strip()
          assert mount_type == "ramfs", f"Expected ramfs, got '{mount_type}'"
          print("✓ /run/secrets and /run/user-secrets are ramfs")

          # ── Test 2: Service secrets decrypted at boot via ML-KEM-768 + X25519 ─
          result = machine.succeed("cat /run/secrets/test-generator/service-secret").strip()
          assert result == "per-machine-service-secret", f"service-secret: expected 'per-machine-service-secret', got '{result}'"
          print("✓ Per-machine PQ service secret decrypted on boot")

          result = machine.succeed("cat /run/secrets/shared-generator/shared-secret").strip()
          assert result == "shared-secret-content", f"shared-secret: expected 'shared-secret-content', got '{result}'"
          print("✓ Shared PQ service secret decrypted on boot")

          # ── Test 3: User secrets decrypted before user creation ─────
          result = machine.succeed("cat /run/user-secrets/test-generator/user-secret").strip()
          assert result == "per-machine-user-secret", f"user-secret: expected 'per-machine-user-secret', got '{result}'"
          print("✓ PQ user secret decrypted on boot")

          # ── Test 4: Activation secrets (pre-decrypted host-side upload) ─
          result = machine.succeed("cat /etc/secret-vars/activation/test-generator/activation-secret").strip()
          assert result == "activation-secret-content", f"activation-secret: expected 'activation-secret-content', got '{result}'"
          print("✓ PQ activation secret decrypted host-side and uploaded")

          # ── Test 5: Permissions applied ─────────────────────────────
          stat_result = machine.succeed("stat -c '%U:%G' /run/secrets/perm-generator/perm-secret").strip()
          assert stat_result == "nobody:nogroup", f"perm-secret owner: expected 'nobody:nogroup', got '{stat_result}'"

          mode_result = machine.succeed("stat -c '%a' /run/secrets/perm-generator/perm-secret").strip()
          assert mode_result == "440", f"perm-secret mode: expected '440', got '{mode_result}'"

          default_mode = machine.succeed("stat -c '%a' /run/secrets/test-generator/service-secret").strip()
          assert default_mode == "400", f"service-secret mode: expected '400', got '{default_mode}'"
          print("✓ Custom and default permissions applied to PQ secrets")

          # ── Test 6: Machine key exists but is protected ─────────────
          mode = machine.succeed("stat -c '%a' /etc/secret-vars/key.txt").strip()
          assert mode == "600", f"key.txt mode: expected '600', got '{mode}'"
          print("✓ PQ machine key has mode 0600")

          # ── Test 7: Verify we actually exercised the PQ path ────────
          key_content = machine.succeed("cat /etc/secret-vars/key.txt")
          assert "AGE-SECRET-KEY-PQ-1" in key_content, (
              "machine key is not a post-quantum hybrid key; test is not exercising the PQ path"
          )
          print("✓ Confirmed post-quantum hybrid key (AGE-SECRET-KEY-PQ-1) is in use")

          print("")
          print("═══════════════════════════════════════════════════")
          print("  NixOS age backend POST-QUANTUM integration tests")
          print("  passed! Verified ML-KEM-768 + X25519 hybrid")
          print("  decryption at boot, all secret phases, ramfs,")
          print("  and permissions.")
          print("═══════════════════════════════════════════════════")
        '';
      };
    };
}
