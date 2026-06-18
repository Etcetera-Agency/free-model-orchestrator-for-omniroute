## 1. Command/http adapters

- [ ] 1.1 Failing test: command and http adapters return the real Hermes source
  shapes and raise structured errors on failure.
- [ ] 1.2 Implement the command and http inventory adapters.

## 2. Live enumeration

- [ ] 2.1 Failing test: profiles are enumerated by scanning real profile dirs +
  `config.yaml` model (no caller-supplied listing).
- [ ] 2.2 Failing test: `service` consumers are derived from enabled gateway
  platforms config.
- [ ] 2.3 Implement live profile enumeration and gateway-platform services.

## 3. Fixtures and validation

- [ ] 3.1 Capture inventory fixtures from a live Hermes deployment where feasible.
- [ ] 3.2 `openspec validate finish-hermes-inventory-adapters --strict` passes.
