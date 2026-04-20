{
  inputs.clan-core.url = "https://__replace__";
  inputs.nixpkgs.url = "https://__replace__";
  inputs.clan-core.inputs.nixpkgs.follows = "nixpkgs";
  inputs.systems.url = "https://__systems__";
  inputs.systems.flake = false;

  outputs =
    {
      self,
      clan-core,
      nixpkgs,
      systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;

      linuxSystems = lib.filter (lib.hasSuffix "linux") (import systems);

      # Same key pair as in pkgs/clan-cli/clan_cli/tests/age_keys.py.
      # Inlined here because the child flake cannot read sibling asset
      # directories and the wrapper used to set this from the parent flake.
      ageRecipient = "age1pq1j726rd9s0l4zze44kfc0kuues44vergmcew45ral7vm9pg987z4rtak9nhkd2zj2xecjq3jwqpayp0w520tmysklzrqxvdswageghlrry9zxcvnpjg4ugetan62f089gjtvl9vaspqumpyejch9ftkhsdncyrp4ajvpedqdvj0fgx8hns7tdns9lgw6ypxalzq3tl2qgdsa8x0t3cc694a40qwm9pd2x3xtpyr3u58zwclzy8k4ks35tz5nx4ql0zkmq52taafama0gspjt7ny2hv6fk2wwdm9gg6zec80npr9pqzg6h43gqfvp63se8v8042xhzg2q4rap20zesm7fnvxdmcdld2a7xkk2g30d47rln3cguqkscszz0zgmw23cygn5fxqplyswwxswv5ddztcjy7clpgnu6dy6slv667e4ma6qz24x5c2y42yhuu6jsfzvcmr596a0ckptz0q0a2uzv2qf0zpcsj0qps8ps9wh5q3k0fesy5n2n4ekz3f2mdq4rmw4834j76afuzve8dvm2xq2hefvd46caxh23py5zyphfjup60xr8x6c9nrmtz7scrgjhnjvhvyay0vf5tfk940djy4pmvzlf8de3qxykkcgqg0ex0pp05elhnd2ne9vpt2g3k7qf86x8hj5n20xkj757hfufrzeux2lfy64guvjhy35mzm5hghl8ravkhdtp7ww746gmpmpnd23u3gfs9wm9qcpa4zn4qf22a3q9fw05ezp2hw33xuru3vq4qzxrvwanx03anqdsfxtx84tutgt2sfh5vw8lfwh93aztfwnv6pzs9952sfa27p9t26s32r3nntvjdmv4kr780pteju4kcwty9udv0xlzq6tk33yscx97nlthz3pc30tehdmyw3z7vdd27528ty0xnwt6x4azydrzs5f24pf85ltpj4xnkc0fnyccysnvnlfmv0xu0pffjuq3evdzn5vaz7krghsfjtlm0tmhdv9cejrllvf3fltunfs5sjfs3yx5e9a0e6t2v92z49yjsap8y59fg5rqlsvk2sc2rm5t4tteljkcas4yr6wtvyksqffnygcvnt89mv5c92ppnslgqh63ndcmgaauzat4nugr2ewnwe5my8u0wsvjj6a5md7vx5h2vnr99tg0mz7nexqra7gew4t98eylw09qldf6hxu4z8zevpw35csttr29epn2kvq4pwgk2hkr8ejtsmhqf0rv4mzk2d5ng3a5xsde039gz45p9j3np7gx9hpmkxy6vdwu2jg3gkrh2qrfmmnsygpmvqna7q4pq322gwyy0zd90ed953nywu2nwa9ay4gcf8tvsjs2vyyd65dgtuj70lckq2arnst3tsvqax2p0delsgq4wlk43q9acp60dxtvtdcl4tc60rnq98xkzv5umgpxkzvrgy930prv8psykj8et94wyvfr8z7zh2sc0tvvza5n6wt6q2fy2pt6655z0ma9dr47pv4mhsga5wufm32eq4lw2j3lkqernp6gftmfyzxv2w9txnpac772a3shf2yrtt5zvp4ej5sgqq29q6cp9awyh24qvgg9q6hfmgx8s46crnufdxmhj4ewfnftgv6jwp2d346trxyxyxt0qcqrzf326gjnl9fgfcdpsj3npvnkg4jk3tq7hetfz90py0gqylhuwmy3j4caa6ujvarmdlfhf09v599gcay5eu288cpe34h2g7wuvzgmze3vnwv46tmsw7djxd4cje40fkjjwjyneez5t0z0ymxmz9n47j2mcppuk3nnh6rz8s50e35mpk5mtaycj6c8ptv7h3v6w0pg352hqdrrx0kjfx9nssxc2r8qydk7fux7rxm0x0dn7prkjmycwmxcnf5al996dvjeafa9fay6chchn23ywad6fhppgtgvjsmvuudadccp24s8";

      installationMachine = import ./installation-machine.nix { inherit clan-core; };

      # Activation override shared by the age and password-store variants.
      # Their secret backends place activation secrets under
      # /etc/secret-vars/activation/ instead of the sops default
      # /var/lib/sops-nix/activation/.
      etcSecretVarsActivation =
        { lib, ... }:
        {
          system.activationScripts.test-vars-activation.text = lib.mkForce ''
            test -e /etc/secret-vars/activation/test-activation/test || {
              echo "\nTEST ERROR: Activation secret not found!\n" >&2
              exit 1
            }
          '';
        };

      # Variants of the without-system base machine. These do not pre-bake a
      # facter report; the test runs `clan machines init-hardware-config`
      # against them to materialise hardware data inside the sandbox.
      withoutSystemBase = {
        nixpkgs.hostPlatform = lib.head linuxSystems;
        imports = [ installationMachine ];
      };

      withoutSystemMachines = {
        test-install-machine-without-system = withoutSystemBase;

        test-install-machine-without-system-with-age =
          { lib, ... }:
          {
            clan.core.vars.settings.secretStore = lib.mkForce "age";
            # clan-core itself is a sops clan; disabling the consistency
            # check lets the test machines opt into a different backend
            # without tripping cross-check assertions against clan-core.
            clan.core.vars.enableConsistencyCheck = false;
            imports = [
              installationMachine
              etcSecretVarsActivation
            ];
            nixpkgs.hostPlatform = lib.head linuxSystems;
          };

        test-install-machine-without-system-with-password-store =
          { lib, ... }:
          {
            clan.core.vars.settings.secretStore = lib.mkForce "password-store";
            clan.core.vars.enableConsistencyCheck = false;
            imports = [
              installationMachine
              etcSecretVarsActivation
            ];
            nixpkgs.hostPlatform = lib.head linuxSystems;
          };
      };

      # Per-system pre-built variants. Their toplevels are pulled into
      # closureInfo so the in-test `clan machines install` step (with
      # nixos-facter) does not have to rebuild from source.
      perSystemMachines = lib.listToAttrs (
        lib.concatMap (system: [
          {
            name = "test-install-machine-${system}";
            value = {
              hardware.facter.reportPath = import ./facter-report.nix system;
              nixpkgs.hostPlatform = system;
              imports = [ installationMachine ];
            };
          }
          {
            name = "test-install-machine-age-${system}";
            value =
              { lib, ... }:
              {
                hardware.facter.reportPath = import ./facter-report.nix system;
                clan.core.vars.settings.secretStore = lib.mkForce "age";
                clan.core.vars.enableConsistencyCheck = false;
                nixpkgs.hostPlatform = system;
                imports = [ installationMachine ];
              };
          }
        ]) linuxSystems
      );

      machines = withoutSystemMachines // perSystemMachines;

      clan = clan-core.lib.clan {
        inherit self;
        inherit machines;
        vars.settings.recipients.hosts.test-install-machine-without-system-with-age = [
          ageRecipient
        ];
        inventory = {
          meta.name = "test-installation";
          meta.domain = "test-installation";
          machines = lib.mapAttrs (_: _: { }) machines;
        };
      };
    in
    {
      inherit (clan.config) nixosConfigurations nixosModules clanInternals;
    };
}
