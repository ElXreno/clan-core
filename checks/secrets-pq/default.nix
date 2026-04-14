{
  name = "secrets-pq";

  nodes.machine =
    { self, config, ... }:
    {
      # Post-quantum hybrid age machine key (ML-KEM-768 + X25519).
      # The matching sops files under sops/ are encrypted to the corresponding
      # age1pq1... recipient, exercising the PQ decryption path end-to-end.
      environment.etc."privkey.age".source = ./key.age;
      imports = [ (self.nixosModules.clanCore) ];
      environment.etc."secret".source = config.sops.secrets.secret.path;
      environment.etc."group-secret".source = config.sops.secrets.group-secret.path;
      environment.etc."secret-sops-file".text = toString config.sops.secrets.secret.sopsFile;
      environment.etc."secret-sops-file-legacy".text = toString (
        config.clan.core.settings.directory + "/sops/secrets/secret/secret"
      );
      sops.age.keyFile = "/etc/privkey.age";

      clan.core.settings.directory = "${./.}";

      networking.hostName = "machine";
    };
  testScript = ''
    # Sanity check: fail early if the fixture is not a PQ identity.
    machine.succeed(
      "grep -q '^AGE-SECRET-KEY-PQ-1' /etc/privkey.age"
      " || (echo 'fixture is not a post-quantum identity' >&2; false)"
    )
    print("✓ /etc/privkey.age is a post-quantum hybrid identity")

    # End-to-end: sops-install-secrets must decrypt an
    # mlkem768x25519-wrapped data key at activation time.
    result = machine.succeed("cat /etc/secret").strip()
    assert result == "foo", f"secret: expected 'foo', got {result!r}"
    print("✓ sops-nix decrypted PQ-wrapped per-machine secret at boot")

    result = machine.succeed("cat /etc/group-secret").strip()
    assert result == "foo", f"group-secret: expected 'foo', got {result!r}"
    print("✓ sops-nix decrypted PQ-wrapped group-addressed secret at boot")

    # Path resolution through config.sops.secrets.*.sopsFile must match what
    # clanCore auto-discovers from the flake directory.
    machine.succeed(
      '[ "$(cat /etc/secret-sops-file)" != "$(cat /etc/secret-sops-file-legacy)" ]'
    )
    print("✓ sopsFile path resolves via the Nix store, not the raw flake path")
  '';
}
