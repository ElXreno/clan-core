{
  config,
  self,
  lib,
  ...
}:
{

  # The purpose of this test is to ensure `clan machines install` works
  # for machines that don't have a hardware config yet.

  # If this test starts failing it could be due to the `facter.json` being out of date
  # you can get a new one by adding
  # client.fail("cat test-flake/machines/test-install-machine/facter.json >&2")
  # to the installation test.
  # Age recipients for the age installation test.
  # Uses the same key pair as pkgs/clan-cli/clan_cli/tests/age_keys.py
  clan.vars.settings.recipients.hosts.test-install-machine-without-system-with-age = [
    "age1pq1j726rd9s0l4zze44kfc0kuues44vergmcew45ral7vm9pg987z4rtak9nhkd2zj2xecjq3jwqpayp0w520tmysklzrqxvdswageghlrry9zxcvnpjg4ugetan62f089gjtvl9vaspqumpyejch9ftkhsdncyrp4ajvpedqdvj0fgx8hns7tdns9lgw6ypxalzq3tl2qgdsa8x0t3cc694a40qwm9pd2x3xtpyr3u58zwclzy8k4ks35tz5nx4ql0zkmq52taafama0gspjt7ny2hv6fk2wwdm9gg6zec80npr9pqzg6h43gqfvp63se8v8042xhzg2q4rap20zesm7fnvxdmcdld2a7xkk2g30d47rln3cguqkscszz0zgmw23cygn5fxqplyswwxswv5ddztcjy7clpgnu6dy6slv667e4ma6qz24x5c2y42yhuu6jsfzvcmr596a0ckptz0q0a2uzv2qf0zpcsj0qps8ps9wh5q3k0fesy5n2n4ekz3f2mdq4rmw4834j76afuzve8dvm2xq2hefvd46caxh23py5zyphfjup60xr8x6c9nrmtz7scrgjhnjvhvyay0vf5tfk940djy4pmvzlf8de3qxykkcgqg0ex0pp05elhnd2ne9vpt2g3k7qf86x8hj5n20xkj757hfufrzeux2lfy64guvjhy35mzm5hghl8ravkhdtp7ww746gmpmpnd23u3gfs9wm9qcpa4zn4qf22a3q9fw05ezp2hw33xuru3vq4qzxrvwanx03anqdsfxtx84tutgt2sfh5vw8lfwh93aztfwnv6pzs9952sfa27p9t26s32r3nntvjdmv4kr780pteju4kcwty9udv0xlzq6tk33yscx97nlthz3pc30tehdmyw3z7vdd27528ty0xnwt6x4azydrzs5f24pf85ltpj4xnkc0fnyccysnvnlfmv0xu0pffjuq3evdzn5vaz7krghsfjtlm0tmhdv9cejrllvf3fltunfs5sjfs3yx5e9a0e6t2v92z49yjsap8y59fg5rqlsvk2sc2rm5t4tteljkcas4yr6wtvyksqffnygcvnt89mv5c92ppnslgqh63ndcmgaauzat4nugr2ewnwe5my8u0wsvjj6a5md7vx5h2vnr99tg0mz7nexqra7gew4t98eylw09qldf6hxu4z8zevpw35csttr29epn2kvq4pwgk2hkr8ejtsmhqf0rv4mzk2d5ng3a5xsde039gz45p9j3np7gx9hpmkxy6vdwu2jg3gkrh2qrfmmnsygpmvqna7q4pq322gwyy0zd90ed953nywu2nwa9ay4gcf8tvsjs2vyyd65dgtuj70lckq2arnst3tsvqax2p0delsgq4wlk43q9acp60dxtvtdcl4tc60rnq98xkzv5umgpxkzvrgy930prv8psykj8et94wyvfr8z7zh2sc0tvvza5n6wt6q2fy2pt6655z0ma9dr47pv4mhsga5wufm32eq4lw2j3lkqernp6gftmfyzxv2w9txnpac772a3shf2yrtt5zvp4ej5sgqq29q6cp9awyh24qvgg9q6hfmgx8s46crnufdxmhj4ewfnftgv6jwp2d346trxyxyxt0qcqrzf326gjnl9fgfcdpsj3npvnkg4jk3tq7hetfz90py0gqylhuwmy3j4caa6ujvarmdlfhf09v599gcay5eu288cpe34h2g7wuvzgmze3vnwv46tmsw7djxd4cje40fkjjwjyneez5t0z0ymxmz9n47j2mcppuk3nnh6rz8s50e35mpk5mtaycj6c8ptv7h3v6w0pg352hqdrrx0kjfx9nssxc2r8qydk7fux7rxm0x0dn7prkjmycwmxcnf5al996dvjeafa9fay6chchn23ywad6fhppgtgvjsmvuudadccp24s8"
  ];

  clan.machines = {
    test-install-machine-without-system-with-password-store =
      { lib, ... }:
      {
        clan.core.vars.settings.secretStore = lib.mkForce "password-store";
        # Temporary Hack!!
        # Disable the consistency check between clan-core and this machine.
        # Since clan-core is a clan which uses sops, we need to disable assertions.
        clan.core.vars.enableConsistencyCheck = false;

        # Override from test-install-machine-without-system
        system.activationScripts.test-vars-activation.text = lib.mkForce ''
          test -e /etc/secret-vars/activation/test-activation/test || {
            echo "\nTEST ERROR: Activation secret not found!\n" >&2
            exit 1
          }
        '';

        imports = [
          ./installation-machine.nix
        ];
      };
    test-install-machine-without-system = ./installation-machine.nix;
    test-install-machine-without-system-with-age =
      { lib, ... }:
      {
        clan.core.vars.settings.secretStore = lib.mkForce "age";
        # Disable the consistency check between clan-core and this machine.
        # Since clan-core is a clan which uses sops, we need to disable assertions.
        clan.core.vars.enableConsistencyCheck = false;

        # Override from test-install-machine-without-system:
        # age activation secrets live at /etc/secret-vars/activation/
        system.activationScripts.test-vars-activation.text = lib.mkForce ''
          test -e /etc/secret-vars/activation/test-activation/test || {
            echo "\nTEST ERROR: Activation secret not found!\n" >&2
            exit 1
          }
        '';

        imports = [
          ./installation-machine.nix
        ];
      };
  }
  // (lib.listToAttrs (
    lib.map (
      system:
      lib.nameValuePair "test-install-machine-${system}" {
        # !!! Important do not add any configuration here
        # This is one of ~10 shallow abstractions over
        # flake.nixosModules.test-install-machine-without-system
        hardware.facter.reportPath = import ./facter-report.nix system;
        imports = [ ./installation-machine.nix ];
      }
    ) (lib.filter (lib.hasSuffix "linux") config.systems)
  ))
  // (lib.listToAttrs (
    lib.map (
      system:
      lib.nameValuePair "test-install-machine-age-${system}" {
        # Variant with age backend, used only for closureInfo to ensure
        # age-specific packages (decrypt-age-secrets, etc.) are in the store.
        hardware.facter.reportPath = import ./facter-report.nix system;
        clan.core.vars.settings.secretStore = lib.mkForce "age";
        clan.core.vars.enableConsistencyCheck = false;
        imports = [ ./installation-machine.nix ];
      }
    ) (lib.filter (lib.hasSuffix "linux") config.systems)
  ));

  perSystem =
    {
      pkgs,
      ...
    }:
    let
      clan-core-flake = self.filter {
        name = "clan-core-flake-filtered";
        include = [
          "flake.nix"
          "flake.lock"
          "checks"
          "clanServices"
          "darwinModules"
          "flakeModules"
          "lib"
          "modules"
          "nixosModules"
        ];
      };
      closureInfo = pkgs.closureInfo {
        rootPaths = [
          clan-core-flake
          self.nixosConfigurations."test-install-machine-${pkgs.stdenv.hostPlatform.system}".config.system.build.toplevel
          self.nixosConfigurations."test-install-machine-${pkgs.stdenv.hostPlatform.system}".config.system.build.initialRamdisk
          self.nixosConfigurations."test-install-machine-${pkgs.stdenv.hostPlatform.system}".config.system.build.diskoScript
          # Age backend variant — ensures age-specific packages are in the store
          self.nixosConfigurations."test-install-machine-age-${pkgs.stdenv.hostPlatform.system}".config.system.build.toplevel
          pkgs.stdenv.drvPath
          pkgs.bash.drvPath
          pkgs.buildPackages.lndir
          pkgs.makeShellWrapper
          # Needed for password-store
          pkgs.shellcheck-minimal
          pkgs.move-mount-beneath
        ]
        ++ builtins.map (i: i.outPath) (builtins.attrValues self.inputs)
        ++ builtins.map (import ./facter-report.nix) (lib.filter (lib.hasSuffix "linux") config.systems);
      };
    in
    {
      legacyPackages.closureInfo = closureInfo;
      # On aarch64-linux, hangs on reboot with after installation:
      # vm-test-run-test-installation-> installer # [  288.002871] reboot: Restarting system
      # vm-test-run-test-installation-> server # [test-install-machine] ### Done! ###
      # vm-test-run-test-installation-> server # [test-install-machine] + step 'Done!'
      # vm-test-run-test-installation-> server # [test-install-machine] + echo '### Done! ###'
      # vm-test-run-test-installation-> server # [test-install-machine] + rm -rf /tmp/tmp.qb16EAq7hJ
      # vm-test-run-test-installation-> (finished: must succeed: clan machines install --debug --flake test-flake --yes test-install-machine --target-host root@installer --update-hardware-config nixos-facter >&2, in 154.62 seconds)
      # vm-test-run-test-installation-> target: starting vm
      # vm-test-run-test-installation-> target: QEMU running (pid 144)
      # vm-test-run-test-installation-> target: waiting for unit multi-user.target
      # vm-test-run-test-installation-> target: waiting for the VM to finish booting
      # vm-test-run-test-installation-> target: Guest root shell did not produce any data yet...
      # vm-test-run-test-installation-> target:   To debug, enter the VM and run 'systemctl status backdoor.service'.
      checks =
        let
          # Use nix 2.30 for clan machines install to avoid directory permission canonicalization issue
          # Nix 2.31+ (commit c38987e04) always tries to chmod directories to 0555
          # during nix copy operations, which fails with "Operation not permitted"
          # This patched clan-cli is ONLY used for 'clan machines install' command
          installTestPkgs = pkgs.extend (
            final: prev: {
              # Override nixos-anywhere to use nix 2.30 for nix copy operations
              nixos-anywhere = prev.nixos-anywhere.override {
                nix = prev.nixVersions.nix_2_30;
              };
              # Override clan-cli to use the pkgs with patched nixos-anywhere
              clan-cli-full = self.packages.${pkgs.stdenv.hostPlatform.system}.clan-cli-full.override {
                pkgs = final;
              };
            }
          );
          installTestClanCli = installTestPkgs.clan-cli-full;
        in
        pkgs.lib.mkIf (pkgs.stdenv.isLinux && !pkgs.stdenv.isAarch64) {
          /*
            Test: Complete Clan machine installation workflow

            This integration test validates the full end-to-end installation process for a Clan machine
            starting from a fresh system without any pre-existing hardware configuration.

            Test flow:

            1. VM Setup: Spawns a target VM running in a NixOS installer environment

            2. Hardware Detection: Executes `clan machines init-hardware-config` to:
               - Detect hardware via SSH connection to the target
               - Generate facter.json with hardware information
               - Create initial machine configuration

            3. Encryption Setup: Runs `clan vars keygen` to generate:
               - SOPS encryption keys for secret management
               - Machine-specific key material

            4. Full Installation: Executes `clan machines install` which performs:
               - Disk partitioning using disko (tests partitioning-time secrets)
               - NixOS system installation with the generated config
               - Secret deployment for both partitioning and activation phases
               - Hardware config update using nixos-facter backend

            5. Verification:
               - Gracefully shuts down the installer VM
               - Boots a new VM from the installed disk image
               - Verifies the installation succeeded by checking for /etc/install-successful

            Objectives:

            - Validates the most common deployment scenario: installing on bare metal/VMs
              without pre-existing hardware configuration files
            - Tests the integration between clan CLI, nixos-anywhere, disko, and sops
            - Ensures secrets are properly deployed at the right stages (partitioning vs activation)
            - Verifies that hardware auto-detection (facter) works correctly

            Note: Uses Nix 2.30 to work around chmod permission issues in Nix 2.31+
          */
          nixos-test-installation = self.clanLib.test.baseTest {
            name = "installation";
            nodes.target = (import ./test-helpers.nix { inherit lib pkgs self; }).target;
            extraPythonPackages = _p: [
              self.legacyPackages.${pkgs.stdenv.hostPlatform.system}.nixosTestLib
            ];

            testScript = ''
              import tempfile
              import os
              import subprocess
              from nixos_test_lib.ssh import setup_ssh_connection # type: ignore[import-untyped]
              from nixos_test_lib.nix_setup import prepare_test_flake # type: ignore[import-untyped]

              def create_test_machine(oldmachine, qemu_test_bin: str, **kwargs):
                  """Create a new test machine from an installed disk image"""
                  start_command = [
                      f"{qemu_test_bin}/bin/qemu-kvm",
                      "-cpu",
                      "max",
                      "-m",
                      "3048",
                      "-virtfs",
                      "local,path=/nix/store,security_model=none,mount_tag=nix-store",
                      "-drive",
                      f"file={oldmachine.state_dir}/target.qcow2,id=drive1,if=none,index=1,werror=report",
                      "-device",
                      "virtio-blk-pci,drive=drive1",
                      "-netdev",
                      "user,id=net0",
                      "-device",
                      "virtio-net-pci,netdev=net0",
                  ]
                  machine = create_machine(start_command=" ".join(start_command), **kwargs)
                  driver.machines.append(machine)
                  return machine

              target.start()

              # Set up test environment
              with tempfile.TemporaryDirectory() as temp_dir:
                  # Prepare test flake and Nix store
                  flake_dir, _ = prepare_test_flake(
                      temp_dir,
                      "${clan-core-flake}",
                      "${closureInfo}"
                  )

                  # Set up SSH connection
                  ssh_conn = setup_ssh_connection(
                      target,
                      temp_dir,
                      "${../assets/ssh/privkey}"
                  )

                  # Run clan init-hardware-config from host using port forwarding
                  clan_cmd = [
                      "${self.packages.${pkgs.stdenv.hostPlatform.system}.clan-cli-full}/bin/clan",
                      "machines",
                      "init-hardware-config",
                      "--debug",
                      "--flake", str(flake_dir),
                      "--yes", "test-install-machine-without-system",
                      "--host-key-check", "none",
                      "--target-host", f"nonrootuser@localhost:{ssh_conn.host_port}",
                      "-i", ssh_conn.ssh_key,
                      "--option", "store", os.environ['CLAN_TEST_STORE']
                  ]
                  subprocess.run(clan_cmd, check=True)

                  # Run clan vars keygen to generate sops keys
                  print("Starting 'clan vars keygen'...")
                  clan_cmd = [
                      "${installTestClanCli}/bin/clan",
                      "vars",
                      "keygen",
                      "--debug",
                      "--flake", str(flake_dir),
                  ]
                  subprocess.run(clan_cmd, check=True)

                  # Run clan install from host using port forwarding
                  print("Starting 'clan machines install'...")
                  clan_cmd = [
                      "${installTestClanCli}/bin/clan",
                      "machines",
                      "install",
                      "--phases", "disko,install",
                      "--debug",
                      "--flake", str(flake_dir),
                      "--yes",
                      "test-install-machine-without-system",
                      "--target-host", f"nonrootuser@localhost:{ssh_conn.host_port}",
                      "-i", ssh_conn.ssh_key,
                      "--option", "store", os.environ['CLAN_TEST_STORE'],
                      "--update-hardware-config", "nixos-facter",
                      "--no-persist-state",
                  ]
                  subprocess.run(clan_cmd, check=True)

              # Shutdown the installer machine gracefully
              try:
                  target.shutdown()
              except BrokenPipeError:
                  # qemu has already exited
                  target.connected = False

              # Create a new machine instance that boots from the installed system
              installed_machine = create_test_machine(target, "${pkgs.qemu_test}", name="after_install")
              installed_machine.start()
              installed_machine.wait_for_unit("multi-user.target")
              installed_machine.succeed("test -f /etc/install-successful")
              installed_machine.shutdown()
            '';
          } { inherit pkgs self; };

          # With age backend
          nixos-test-installation-age = self.clanLib.test.baseTest {
            name = "installation";

            nodes.target = {
              imports = [ (import ./test-helpers.nix { inherit lib pkgs; }).target ];
            };

            extraPythonPackages = _p: [
              self.legacyPackages.${pkgs.stdenv.hostPlatform.system}.nixosTestLib
            ];

            testScript = ''
              import tempfile
              import os
              import subprocess
              from pathlib import Path
              from nixos_test_lib.ssh import setup_ssh_connection # type: ignore[import-untyped]
              from nixos_test_lib.nix_setup import prepare_test_flake # type: ignore[import-untyped]

              # Same key pair as in pkgs/clan-cli/clan_cli/tests/age_keys.py
              age_privkey = "AGE-SECRET-KEY-PQ-1KF6PDF5SY3PMHNHMV0Q0EWUSYEQ6Y9PWQ460ENUWA7M265NUUAYS9FTYJJ"

              def create_test_machine(oldmachine, qemu_test_bin: str, **kwargs):
                  """Create a new test machine from an installed disk image"""
                  start_command = [
                      f"{qemu_test_bin}/bin/qemu-kvm",
                      "-cpu",
                      "max",
                      "-m",
                      "3048",
                      "-virtfs",
                      "local,path=/nix/store,security_model=none,mount_tag=nix-store",
                      "-drive",
                      f"file={oldmachine.state_dir}/target.qcow2,id=drive1,if=none,index=1,werror=report",
                      "-device",
                      "virtio-blk-pci,drive=drive1",
                      "-netdev",
                      "user,id=net0",
                      "-device",
                      "virtio-net-pci,netdev=net0",
                  ]
                  machine = create_machine(start_command=" ".join(start_command), **kwargs)
                  driver.machines.append(machine)
                  return machine

              target.start()

              # Set up test environment
              with tempfile.TemporaryDirectory() as temp_dir:

                  # Set up age key file
                  age_key_dir = Path(temp_dir) / ".age"
                  age_key_dir.mkdir()
                  age_key_file = age_key_dir / "key.txt"
                  age_key_file.write_text(age_privkey)
                  os.environ["AGE_KEYFILE"] = str(age_key_file)

                  # Prepare test flake and Nix store
                  flake_dir, _ = prepare_test_flake(
                      temp_dir,
                      "${self.packages.${pkgs.stdenv.buildPlatform.system}.clan-core-flake}",
                      "${closureInfo}"
                  )

                  # Set up SSH connection
                  ssh_conn = setup_ssh_connection(
                      target,
                      temp_dir,
                      "${../assets/ssh/privkey}"
                  )

                  # Run clan init-hardware-config from host using port forwarding
                  clan_cmd = [
                      "${self.packages.${pkgs.stdenv.hostPlatform.system}.clan-cli-full}/bin/clan",
                      "machines",
                      "init-hardware-config",
                      "--debug",
                      "--flake", str(flake_dir),
                      "--yes", "test-install-machine-without-system-with-age",
                      "--host-key-check", "none",
                      "--target-host", f"nonrootuser@localhost:{ssh_conn.host_port}",
                      "-i", ssh_conn.ssh_key,
                      "--option", "store", os.environ['CLAN_TEST_STORE']
                  ]
                  subprocess.run(clan_cmd, check=True)

                  # No keygen needed for age backend — machine keys are auto-generated
                  # during 'clan vars generate' / 'clan machines install'

                  # Run clan install from host using port forwarding
                  print("Starting 'clan machines install'...")
                  clan_cmd = [
                      "${installTestClanCli}/bin/clan",
                      "machines",
                      "install",
                      "--phases", "disko,install",
                      "--debug",
                      "--flake", str(flake_dir),
                      "--yes",
                      "test-install-machine-without-system-with-age",
                      "--target-host", f"nonrootuser@localhost:{ssh_conn.host_port}",
                      "-i", ssh_conn.ssh_key,
                      "--option", "store", os.environ['CLAN_TEST_STORE'],
                      "--update-hardware-config", "nixos-facter",
                      "--no-persist-state",
                  ]
                  subprocess.run(clan_cmd, check=True)

              # Shutdown the installer machine gracefully
              try:
                  target.shutdown()
              except BrokenPipeError:
                  # qemu has already exited
                  target.connected = False

              # Create a new machine instance that boots from the installed system
              installed_machine = create_test_machine(target, "${pkgs.qemu_test}", name="after_install")
              installed_machine.start()
              installed_machine.wait_for_unit("multi-user.target")
              installed_machine.succeed("test -f /etc/install-successful")
              installed_machine.shutdown()
            '';
          } { inherit pkgs self; };

          # With password store
          nixos-test-installation-password-store = self.clanLib.test.baseTest {
            name = "installation";

            nodes.target = {
              imports = [ (import ./test-helpers.nix { inherit lib pkgs; }).target ];
            };

            extraPythonPackages = _p: [
              self.legacyPackages.${pkgs.stdenv.hostPlatform.system}.nixosTestLib
            ];

            testScript = ''
              import tempfile
              import os
              # import shutil
              import subprocess
              from pathlib import Path
              from nixos_test_lib.ssh import setup_ssh_connection # type: ignore[import-untyped]
              from nixos_test_lib.nix_setup import prepare_test_flake # type: ignore[import-untyped]

              os.environ["PATH"] = f"""{os.environ.get("PATH")}:${pkgs.passage}/bin:${pkgs.git}/bin:${pkgs.age}/bin"""

              def create_test_machine(oldmachine, qemu_test_bin: str, **kwargs):
                  """Create a new test machine from an installed disk image"""
                  start_command = [
                      f"{qemu_test_bin}/bin/qemu-kvm",
                      "-cpu",
                      "max",
                      "-m",
                      "3048",
                      "-virtfs",
                      "local,path=/nix/store,security_model=none,mount_tag=nix-store",
                      "-drive",
                      f"file={oldmachine.state_dir}/target.qcow2,id=drive1,if=none,index=1,werror=report",
                      "-device",
                      "virtio-blk-pci,drive=drive1",
                      "-netdev",
                      "user,id=net0",
                      "-device",
                      "virtio-net-pci,netdev=net0",
                  ]
                  machine = create_machine(start_command=" ".join(start_command), **kwargs)
                  driver.machines.append(machine)
                  return machine

              target.start()

              # Set up test environment
              with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as pass_dir:

                  password_store_dir = str(pass_dir + "/pass")
                  Path(password_store_dir).mkdir(parents=True)
                  os.environ["PASSWORD_STORE_DIR"] = password_store_dir

                  # Copied from pkgs/clan-cli/clan_cli/tests/age_keys.py
                  age_pubkey = "age1pq1j726rd9s0l4zze44kfc0kuues44vergmcew45ral7vm9pg987z4rtak9nhkd2zj2xecjq3jwqpayp0w520tmysklzrqxvdswageghlrry9zxcvnpjg4ugetan62f089gjtvl9vaspqumpyejch9ftkhsdncyrp4ajvpedqdvj0fgx8hns7tdns9lgw6ypxalzq3tl2qgdsa8x0t3cc694a40qwm9pd2x3xtpyr3u58zwclzy8k4ks35tz5nx4ql0zkmq52taafama0gspjt7ny2hv6fk2wwdm9gg6zec80npr9pqzg6h43gqfvp63se8v8042xhzg2q4rap20zesm7fnvxdmcdld2a7xkk2g30d47rln3cguqkscszz0zgmw23cygn5fxqplyswwxswv5ddztcjy7clpgnu6dy6slv667e4ma6qz24x5c2y42yhuu6jsfzvcmr596a0ckptz0q0a2uzv2qf0zpcsj0qps8ps9wh5q3k0fesy5n2n4ekz3f2mdq4rmw4834j76afuzve8dvm2xq2hefvd46caxh23py5zyphfjup60xr8x6c9nrmtz7scrgjhnjvhvyay0vf5tfk940djy4pmvzlf8de3qxykkcgqg0ex0pp05elhnd2ne9vpt2g3k7qf86x8hj5n20xkj757hfufrzeux2lfy64guvjhy35mzm5hghl8ravkhdtp7ww746gmpmpnd23u3gfs9wm9qcpa4zn4qf22a3q9fw05ezp2hw33xuru3vq4qzxrvwanx03anqdsfxtx84tutgt2sfh5vw8lfwh93aztfwnv6pzs9952sfa27p9t26s32r3nntvjdmv4kr780pteju4kcwty9udv0xlzq6tk33yscx97nlthz3pc30tehdmyw3z7vdd27528ty0xnwt6x4azydrzs5f24pf85ltpj4xnkc0fnyccysnvnlfmv0xu0pffjuq3evdzn5vaz7krghsfjtlm0tmhdv9cejrllvf3fltunfs5sjfs3yx5e9a0e6t2v92z49yjsap8y59fg5rqlsvk2sc2rm5t4tteljkcas4yr6wtvyksqffnygcvnt89mv5c92ppnslgqh63ndcmgaauzat4nugr2ewnwe5my8u0wsvjj6a5md7vx5h2vnr99tg0mz7nexqra7gew4t98eylw09qldf6hxu4z8zevpw35csttr29epn2kvq4pwgk2hkr8ejtsmhqf0rv4mzk2d5ng3a5xsde039gz45p9j3np7gx9hpmkxy6vdwu2jg3gkrh2qrfmmnsygpmvqna7q4pq322gwyy0zd90ed953nywu2nwa9ay4gcf8tvsjs2vyyd65dgtuj70lckq2arnst3tsvqax2p0delsgq4wlk43q9acp60dxtvtdcl4tc60rnq98xkzv5umgpxkzvrgy930prv8psykj8et94wyvfr8z7zh2sc0tvvza5n6wt6q2fy2pt6655z0ma9dr47pv4mhsga5wufm32eq4lw2j3lkqernp6gftmfyzxv2w9txnpac772a3shf2yrtt5zvp4ej5sgqq29q6cp9awyh24qvgg9q6hfmgx8s46crnufdxmhj4ewfnftgv6jwp2d346trxyxyxt0qcqrzf326gjnl9fgfcdpsj3npvnkg4jk3tq7hetfz90py0gqylhuwmy3j4caa6ujvarmdlfhf09v599gcay5eu288cpe34h2g7wuvzgmze3vnwv46tmsw7djxd4cje40fkjjwjyneez5t0z0ymxmz9n47j2mcppuk3nnh6rz8s50e35mpk5mtaycj6c8ptv7h3v6w0pg352hqdrrx0kjfx9nssxc2r8qydk7fux7rxm0x0dn7prkjmycwmxcnf5al996dvjeafa9fay6chchn23ywad6fhppgtgvjsmvuudadccp24s8"
                  age_privkey = "AGE-SECRET-KEY-PQ-1KF6PDF5SY3PMHNHMV0Q0EWUSYEQ6Y9PWQ460ENUWA7M265NUUAYS9FTYJJ"

                  age_key_dir = Path(pass_dir + "/.age")
                  age_key_dir.mkdir()
                  age_key_file = age_key_dir / "key.txt"
                  age_key_file.write_text(age_privkey)

                  # Create .age-recipients file for passage (passage uses this instead of .gpg-id)
                  Path(password_store_dir + "/.age-recipients").write_text(f"{age_pubkey}\n")

                  # Passage uses PASSAGE_DIR (not PASSWORD_STORE_DIR like pass does)
                  os.environ["PASSAGE_DIR"] = str(password_store_dir)
                  # Set the age identities file for passage
                  os.environ["PASSAGE_IDENTITIES_FILE"] = str(age_key_file)

                  # Initialize password store as a git repository
                  # ---

                  # Path(f"{password_store_dir}/.passage").mkdir(parents=True)
                  # subprocess.run(["age-keygen", "-o", f"{password_store_dir}/.passage/identities"], cwd=password_store_dir, check=True)

                  subprocess.run(["git", "init"], cwd=password_store_dir, check=True)
                  subprocess.run(
                      ["git", "config", "user.email", "test@example.com"],
                      cwd=password_store_dir,
                      check=True,
                  )
                  subprocess.run(
                      ["git", "config", "user.name", "Test User"],
                      cwd=password_store_dir,
                      check=True,
                  )

                  # --- End of password store initialization
                  ###

                  # Prepare test flake and Nix store
                  flake_dir, _ = prepare_test_flake(
                      temp_dir,
                      "${self.packages.${pkgs.stdenv.buildPlatform.system}.clan-core-flake}",
                      "${closureInfo}"
                  )

                  # Set up SSH connection
                  ssh_conn = setup_ssh_connection(
                      target,
                      temp_dir,
                      "${../assets/ssh/privkey}"
                  )

                  # Run clan init-hardware-config from host using port forwarding
                  clan_cmd = [
                      "${self.packages.${pkgs.stdenv.hostPlatform.system}.clan-cli-full}/bin/clan",
                      "machines",
                      "init-hardware-config",
                      "--debug",
                      "--flake", str(flake_dir),
                      "--yes", "test-install-machine-without-system-with-password-store",
                      "--host-key-check", "none",
                      "--target-host", f"nonrootuser@localhost:{ssh_conn.host_port}",
                      "-i", ssh_conn.ssh_key,
                      "--option", "store", os.environ['CLAN_TEST_STORE']
                  ]
                  subprocess.run(clan_cmd, check=True)

                  # Run clan install from host using port forwarding
                  print("Starting 'clan machines install'...")
                  clan_cmd = [
                      "${installTestClanCli}/bin/clan",
                      "machines",
                      "install",
                      "--phases", "disko,install",
                      "--debug",
                      "--flake", str(flake_dir),
                      "--yes",
                      "test-install-machine-without-system-with-password-store",
                      "--target-host", f"nonrootuser@localhost:{ssh_conn.host_port}",
                      "-i", ssh_conn.ssh_key,
                      "--option", "store", os.environ['CLAN_TEST_STORE'],
                      "--update-hardware-config", "nixos-facter",
                      "--no-persist-state",
                  ]
                  subprocess.run(clan_cmd, check=True)

              # Shutdown the installer machine gracefully
              try:
                  target.shutdown()
              except BrokenPipeError:
                  # qemu has already exited
                  target.connected = False

              # Create a new machine instance that boots from the installed system
              installed_machine = create_test_machine(target, "${pkgs.qemu_test}", name="after_install")
              installed_machine.start()
              installed_machine.wait_for_unit("multi-user.target")
              installed_machine.succeed("test -f /etc/install-successful")
              installed_machine.shutdown()
            '';
          } { inherit pkgs self; };

          nixos-test-update-hardware-configuration = self.clanLib.test.baseTest {
            name = "update-hardware-configuration";
            nodes.target = (import ./test-helpers.nix { inherit lib pkgs self; }).target;
            extraPythonPackages = _p: [
              self.legacyPackages.${pkgs.stdenv.hostPlatform.system}.nixosTestLib
            ];

            testScript = ''
              import tempfile
              import os
              import subprocess
              from nixos_test_lib.ssh import setup_ssh_connection # type: ignore[import-untyped]
              from nixos_test_lib.nix_setup import prepare_test_flake # type: ignore[import-untyped]

              target.start()

              # Set up test environment
              with tempfile.TemporaryDirectory() as temp_dir:
                  # Prepare test flake and Nix store
                  flake_dir, _ = prepare_test_flake(
                      temp_dir,
                      "${clan-core-flake}",
                      "${closureInfo}"
                  )

                  # Set up SSH connection
                  ssh_conn = setup_ssh_connection(
                      target,
                      temp_dir,
                      "${../assets/ssh/privkey}"
                  )

                  # Verify files don't exist initially
                  hw_config_file = os.path.join(flake_dir, "machines/test-install-machine/hardware-configuration.nix")
                  facter_file = os.path.join(flake_dir, "machines/test-install-machine/facter.json")

                  assert not os.path.exists(hw_config_file), "hardware-configuration.nix should not exist initially"
                  assert not os.path.exists(facter_file), "facter.json should not exist initially"

                  # Test facter backend
                  clan_cmd = [
                      "${self.packages.${pkgs.stdenv.hostPlatform.system}.clan-cli-full}/bin/clan",
                      "machines",
                      "update-hardware-config",
                      "--debug",
                      "--flake", ".",
                      "--host-key-check", "none",
                      "test-install-machine-without-system",
                      "-i", ssh_conn.ssh_key,
                      "--option", "store", os.environ['CLAN_TEST_STORE'],
                      "--target-host", f"nonrootuser@localhost:{ssh_conn.host_port}",
                      "--yes"
                  ]

                  result = subprocess.run(clan_cmd, capture_output=True, cwd=flake_dir)
                  if result.returncode != 0:
                      print(f"Clan update-hardware-config failed: {result.stderr.decode()}")
                      raise Exception(f"Clan update-hardware-config failed with return code {result.returncode}")

                  facter_without_system_file = os.path.join(flake_dir, "machines/test-install-machine-without-system/facter.json")
                  assert os.path.exists(facter_without_system_file), "facter.json should exist after update"
                  os.remove(facter_without_system_file)

                  # Test nixos-generate-config backend
                  clan_cmd = [
                      "${self.packages.${pkgs.stdenv.hostPlatform.system}.clan-cli-full}/bin/clan",
                      "machines",
                      "update-hardware-config",
                      "--debug",
                      "--backend", "nixos-generate-config",
                      "--host-key-check", "none",
                      "--flake", ".",
                      "test-install-machine-without-system",
                      "-i", ssh_conn.ssh_key,
                      "--option", "store", os.environ['CLAN_TEST_STORE'],
                      "--target-host",
                      f"nonrootuser@localhost:{ssh_conn.host_port}",
                      "--yes"
                  ]

                  result = subprocess.run(clan_cmd, capture_output=True, cwd=flake_dir)
                  if result.returncode != 0:
                      print(f"Clan update-hardware-config (nixos-generate-config) failed: {result.stderr.decode()}")
                      raise Exception(f"Clan update-hardware-config failed with return code {result.returncode}")

                  hw_config_without_system_file = os.path.join(flake_dir, "machines/test-install-machine-without-system/hardware-configuration.nix")
                  assert os.path.exists(hw_config_without_system_file), "hardware-configuration.nix should exist after update"
            '';
          } { inherit pkgs self; };

        };
    };
}
