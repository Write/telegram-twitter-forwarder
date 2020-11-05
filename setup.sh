rm -rf venv/
virtualenv -p python3 venv
. venv/bin/activate
. secrets.env
pip install -r requirements.txt
