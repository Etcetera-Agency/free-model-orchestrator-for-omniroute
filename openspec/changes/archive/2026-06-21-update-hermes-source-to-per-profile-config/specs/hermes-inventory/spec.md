# hermes-inventory Specification

## ADDED Requirements

### Requirement: Model slots are read from per-profile config

The system SHALL read every Hermes profile's model slots from that profile's own
`<profile_dir>/config.yaml`, not from the `hermes profile list` summary. The
profile list (`ProfileInfo`) SHALL be used only to enumerate profile name, path
and `gateway_running`; it does not carry auxiliary slots and therefore is not the
slot source.

The reader SHALL resolve the main combo from the `model` key in two shapes: a
mapping (`model.default` is the combo id) and the legacy bare string. An
unconfigured profile whose `model` is the empty-string sentinel `""` SHALL yield
no main combo without error. The reader SHALL carry the raw `auxiliary` mapping
through unchanged for downstream consumer enumeration.

#### Scenario: Model slots are read from per-profile config
- GIVEN a profile whose `config.yaml` sets `model.default` to a combo id
- WHEN the inventory reads that profile
- THEN the main combo is taken from `config.yaml` (`model.default`), not from the
  profile-list summary `model` field
- AND the profile's `auxiliary` mapping is available unchanged to later stages

#### Scenario: Auxiliary slots are absent from the profile list
- GIVEN the `hermes profile list` summary (`ProfileInfo`) for a profile that has
  an `auxiliary:` block in its `config.yaml`
- WHEN the inventory enumerates profiles
- THEN the list summary is used only for name, path and gateway state
- AND the auxiliary slots are obtained from the profile's `config.yaml`, since
  the list summary carries none

#### Scenario: Unconfigured profile model is tolerated
- GIVEN a fresh profile whose `config.yaml` has `model: ""`
- WHEN the inventory reads that profile
- THEN the main combo resolves to none without raising
- AND the profile is still enumerated for its auxiliary slots and gateway state
