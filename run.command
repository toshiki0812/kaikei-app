#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "初回起動: 仮想環境を作成しています..."
  python3 -m venv venv
  ./venv/bin/pip install --upgrade pip >/dev/null
  ./venv/bin/pip install -r requirements.txt
fi

./venv/bin/streamlit run app.py
