# Catalyst Automation Skeleton

Production-friendly starter for Cisco Catalyst Center (DNA Center) automation with Python.

## Quick start
1) Copy `.env.example` to `.env` and set your values.
2) Edit `settings.yaml` to reflect your site(s).
3) Create and activate a virtual environment, then install deps:
   ```bash
   python -m venv .venv
   . .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4) Try the examples:
   ```bash
   python examples/01_get_inventory.py --csv out/inventory.csv
   python examples/02_run_cmdrunner_lldp.py --device <device-uuid>
   ```

> NOTE: Endpoints here match Catalyst Center style (formerly DNA Center).
> Adjust URLs or payloads per your version's API docs.