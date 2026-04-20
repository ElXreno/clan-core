{ ... }:
let
  module = ./default.nix;
in
{
  clan.modules = {
    coredns = module;
    "@clan/coredns" = module;
  };
  clan.deprecatedModules = [
    "coredns"
    "@clan/coredns"
  ];
}
