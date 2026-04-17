throw ''

  The `coredns` clan service has been moved out of clan-core and now lives in
  the `clan-community` flake:

      https://git.clan.lol/clan/clan-community

  To migrate:

    1. Add `clan-community` to your flake inputs:

         inputs.clan-community.url =
           "https://git.clan.lol/clan/clan-community/archive/main.tar.gz";
         inputs.clan-community.inputs.clan-core.follows = "clan-core";

    2. In your inventory, change the `coredns` instance:

         instances.coredns = {
           module.name  = "coredns";         # drop the `@clan/` prefix
           module.input = "clan-community";  # was "self" (or unset)

           # roles.* stay the same
         };

  The module options (`ip`, `tld`, `services`, roles `server` and `default`)
  are unchanged — only the module source has moved.
''
