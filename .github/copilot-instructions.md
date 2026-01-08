# Copilot / AI agent instructions — PowerTrader AI

Purpose: quick, actionable knowledge to help an AI agent be productive in this repo.

- Big picture
  - The project is a small multi-process trading system with 3 runtime roles:
    - GUI hub: `pt_hub.py` (Tkinter) — central controller and UI, starts other scripts.
    - Runner / Thinker: `pt_thinker.py` — generates multi-timeframe predicted price levels.
    - Trainer: `pt_trainer.py` — builds/updates the pattern/memory files used by the thinker.
    - Trader: `pt_trader.py` — executes buys/sells, writes trade history and ledger.

- Key IPC & file conventions (examples)
  - Hub <-> runners communicate via files in `hub_data/` and per-coin files.
    - `hub_data/runner_ready.json` — runner signals readiness.
    - `hub_data/trade_history.jsonl` — newline-delimited trade events (written by `pt_trader.py`).
    - `hub_data/trader_status.json` — runtime trader state.
  - Per-coin folder files (under `main_neural_dir` / coin subfolders):
    - `memories_<tf>.txt`, `memory_weights_<tf>.txt`, `memory_weights_high_<tf>.txt`, `memory_weights_low_<tf>.txt` (trainer outputs)
    - `neural_perfect_threshold_<tf>.txt`, `trainer_last_training_time.txt`, `trainer_status.json`
    - `low_bound_prices.html`, `high_bound_prices.html` (thinker writes predicted levels; parser is tolerant to commas/brackets)
    - `long_dca_signal.txt`, `short_dca_signal.txt`, and other control flags like `futures_*` files.

- Important conventions & patterns
  - BTC uses the `main_neural_dir` root; other coins live in `<main_dir>/<SYMBOL>` when that folder exists. See `build_coin_folders` (in `pt_hub.py`) and `coin_folder` (in `pt_thinker.py`).
  - The code relies heavily on resilient, plain-text file I/O for state and signaling — prefer using existing `_atomic_write_json` / `_append_jsonl` helpers when modifying files.
  - KuCoin vs REST: `pt_thinker.py` and `pt_hub.py` use the `kucoin` package when available, otherwise fall back to HTTP. The feature flag `USE_KUCOIN_API` can disable the client.
  - Robinhood creds: `pt_trader.py` and `pt_thinker.py` expect `r_key.txt` and `r_secret.txt` next to the scripts; `r_secret.txt` holds a base64-encoded private key — treat as secret.

- Developer workflows (concrete commands)
  - Install deps: `python -m pip install -r requirements.txt`.
  - Run hub (preferred): `python pt_hub.py` — Hub starts thinker then trader when you click Start All.
  - Train a coin from CLI: `python pt_trainer.py BTC` (trainer writes `trainer_status.json` and memory files in the coin folder).
  - Run runner/trader manually for debugging: `python pt_thinker.py` and `python pt_trader.py` (the hub normally launches these; examine `gui_settings.json` for `main_neural_dir` and script overrides).

- Integration & observability
  - External integrations: KuCoin (market candles), Robinhood Trading API (signing with keys). Expect network calls and API error handling.
  - Check `hub_data/` files and per-coin `trainer_status.json` for runtime state and failures.
  - Trainer supports a `killer.txt` flag and throttled writes (`write_threshold_sometimes`, `flush_memory`) — useful to stop or reduce I/O when testing.

- What to look for when changing code
  - Preserve file-format compatibility: thinker/trader/parsers are tolerant to commas/brackets but expect numeric lists in the per-coin files.
  - Respect the BTC-main-folder convention when adding path changes to avoid corrupting BTC data.
  - Use existing helper functions `_atomic_write_json`, `_append_jsonl` and `build_coin_folders` to avoid races.

- Quick references (examples to open)
  - Hub/UI: `pt_hub.py`
  - Runner/Thinker: `pt_thinker.py`
  - Trainer: `pt_trainer.py`
  - Trader: `pt_trader.py`
  - Settings: `gui_settings.json`, `hub_data/`, per-coin files under `PowerTrader_AI/` or configured `main_neural_dir`

If anything here is unclear or you'd like more examples (small patches or typical edit patterns), tell me which area to expand.  