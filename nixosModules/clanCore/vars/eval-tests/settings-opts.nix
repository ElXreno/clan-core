{ lib }:
let
  evalSettings =
    settings:
    (lib.evalModules {
      modules = [
        ../../../../modules/clan/vars/settings-opts.nix
        settings
      ];
    }).config;
in
{
  test_age_option_exists =
    let
      config = evalSettings { };
    in
    {
      expr = config ? age;
      expected = true;
    };

  test_age_post_quantum_default_is_false =
    let
      config = evalSettings { };
    in
    {
      expr = config.age.postQuantum;
      expected = false;
    };

  test_age_post_quantum_can_be_enabled =
    let
      config = evalSettings {
        age.postQuantum = true;
      };
    in
    {
      expr = config.age.postQuantum;
      expected = true;
    };
}
