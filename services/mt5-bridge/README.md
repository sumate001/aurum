# MT5 Bridge

Windows-only service. Runs alongside MetaTrader5 terminal.

## Setup

1. Install Python 3.11 on Windows
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set environment variables:
   ```
   MT5_BRIDGE_API_KEY=your_secret_key
   MT5_ACCOUNT=your_account_number
   MT5_PASSWORD=your_password
   MT5_SERVER=XMGlobal-MT5
   ```
4. Start bridge:
   ```
   uvicorn bridge:app --host 0.0.0.0 --port 8400
   ```
5. Update `.env` on Linux server:
   ```
   MT5_BRIDGE_URL=http://WINDOWS_IP:8400
   MT5_BRIDGE_API_KEY=your_secret_key
   ```
