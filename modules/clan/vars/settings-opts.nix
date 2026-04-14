{ lib, config, ... }:
let
  inherit (lib) mkOption;
  inherit (lib.types)
    str
    path
    bool
    nullOr
    deferredModuleWith
    submoduleWith
    attrsOf
    listOf
    ;

  fileModuleInterface = file: {
    options = {
      name = mkOption {
        type = str;
        description = ''
          name of the public fact
        '';
        readOnly = true;
        default = file.config._module.args.name;
        defaultText = "Name of the file";
      };
      generatorName = mkOption {
        type = str;
        description = ''
          name of the generator
        '';
        # This must be set by the 'generator' (parent of this submodule)
        default = throw "generatorName must be set by the generator";
        defaultText = "Name of the generator that generates this file";
      };
      secret = mkOption {
        description = ''
          Whether the file should be treated as a secret.
        '';
        type = bool;
        default = true;
      };
      flakePath = mkOption {
        description = ''
          The path to the file containing the content of the generated value.
          This will be set automatically
        '';
        type = nullOr path;
        default = null;
      };
      path = mkOption {
        description = ''
          The path to the file containing the content of the generated value.
          This will be set automatically
        '';
        type = str;
        defaultText = ''
          builtins.path {
            name = "$${file.config.generatorName}_$${file.config.name}";
            path = file.config.flakePath;
          }
        '';
        default =
          if file.config.flakePath == null then
            throw "flakePath must be set before accessing path"
          else if !builtins.pathExists file.config.flakePath then
            throw "File '${file.config.name}' of generator '${file.config.generatorName}' does not exist. Try running 'clan vars generate' first."
          else
            builtins.path {
              name = "${file.config.generatorName}_${file.config.name}";
              path = file.config.flakePath;
            };
      };
      exists = mkOption {
        description = ''
          Returns true if the file exists. This is used to guard against reading not set value in evaluation.
          This currently only works for non secret files.
        '';
        type = bool;
        default = if file.config.secret then throw "Cannot determine existence of secret file" else false;
        defaultText = "Throws error because the existence of a secret file cannot be determined";
      };
      value =
        mkOption {
          description = ''
            The content of the generated value.
            Only available if the file is not secret.
          '';
          type = str;
          defaultText = "Throws error because the value of a secret file is not accessible";
        }
        // lib.optionalAttrs file.config.secret {
          default = throw "Cannot access value of secret file";
        };
    };
  };

  storeModule = {
    options.pythonModule = mkOption { type = str; };
  };

in
{
  options = {
    secretStore = mkOption {
      type = lib.types.enum [
        "sops"
        "password-store"
        "age"
        "custom"
      ];
      default = "sops";
      description = ''
        method to store secret vars.
        custom can be used to define a custom secret var store.
      '';
    };

    secretModule = mkOption {
      type = str;
      internal = true;
      description = ''
        the python import path to the secret module
      '';
      default = config.stores.${config.secretStore}.pythonModule;
    };

    # TODO: see if this is the right approach. Maybe revert to secretPathFunction
    fileModule = mkOption {
      type = deferredModuleWith {
        staticModules = [
          fileModuleInterface
          (lib.mkRenamedOptionModule
            [
              "sops"
              "owner"
            ]
            [
              "owner"
            ]
          )
          (lib.mkRenamedOptionModule
            [
              "sops"
              "group"
            ]
            [
              "group"
            ]
          )
        ];
      };
      internal = true;
      description = ''
        A module to be imported in every vars.files.<name> submodule.
        Used by backends to define the `path` attribute.
      '';
      default = { };
    };

    publicStore = mkOption {
      type = lib.types.enum [
        "in_repo"
      ];
      default = "in_repo";
      description = ''
        Method to store public vars.
        Currently only 'in_repo' is supported, which stores public vars in the clan repository.
      '';
    };

    publicModule = mkOption {
      type = str;
      internal = true;
      description = ''
        the python import path to the public module
      '';
      default = config.publicStores.${config.publicStore}.pythonModule;
    };

    stores = mkOption {
      internal = true;
      visible = false;
      type = attrsOf (submoduleWith {
        modules = [ storeModule ];
      });
    };
    publicStores = mkOption {
      internal = true;
      visible = false;
      type = attrsOf (submoduleWith {
        modules = [ storeModule ];
      });
    };

    recipients = mkOption {
      type = lib.types.submodule {
        options = {
          hosts = mkOption {
            type = attrsOf (listOf str);
            default = { };
            description = ''
              Age public keys per host for secret encryption.
              Example:
                recipients.hosts.myhost = [ "age1..." ];
            '';
          };
          default = mkOption {
            type = listOf str;
            default = [ ];
            description = ''
              Fallback age recipients used when no host-specific recipients are configured.
              Only applies to machines without entries in `recipients.hosts`.
            '';
          };
        };
      };
      default = { };
      description = ''
        Age recipients configuration for the age secret store.
      '';
    };

    age = mkOption {
      type = lib.types.submodule {
        options = {
          postQuantum = mkOption {
            type = bool;
            default = false;
            description = ''
              Generate post-quantum hybrid age keys (ML-KEM-768 + X25519) instead
              of classical X25519 when clan-cli creates new admin or machine keys.

              Hybrid keys use HPKE with ML-KEM-768 KEM and X25519 as a classical
              backstop, so an attacker needs to break both algorithms to recover
              encrypted data. This provides protection against future
              cryptographically-relevant quantum computers under the
              store-now-decrypt-later threat model.

              Enabling this flag affects only new key generation; existing
              classical keys are not rotated. To add a post-quantum key to an
              existing admin, use `clan secrets users add-key`. To rotate a
              machine, delete its `sops/machines/<M>` and
              `sops/secrets/<M>-age.key`, then run `clan vars fix <M>`.

              For the sops backend (default), each recipient's data key is
              wrapped independently, so mixing classical and post-quantum
              recipients on the same file is safe and rotation can happen
              incrementally, one machine at a time.

              For the age backend (`secretStore = "age"`, raw `.age` files),
              age refuses to mix post-quantum and classical recipients on a
              single file (error: `incompatible recipients: can't mix
              post-quantum and classic recipients`), because the classical
              recipient would silently downgrade the PQ user's security.
              Rotate every recipient of each secret atomically if you use this
              backend.

              Tradeoffs: post-quantum recipients are ~2 KB (vs ~62 bytes for
              X25519), so every committed `sops/*/secret` file grows by roughly
              that amount per recipient, and git diffs become noisier.
            '';
          };
        };
      };
      default = { };
      description = ''
        Age key generation settings for clan-cli.
      '';
    };

  };

  config.stores = {
    fs = {
      pythonModule = "clan_lib.vars.secret_modules.fs";
    };
    sops = {
      pythonModule = "clan_lib.vars.secret_modules.sops";
    };
    "password-store" = {
      pythonModule = "clan_lib.vars.secret_modules.password_store";
    };
    age = {
      pythonModule = "clan_lib.vars.secret_modules.age";
    };
  };
  config.publicStores = {
    in_repo = {
      pythonModule = "clan_lib.vars.public_modules.in_repo";
    };
  };
}
